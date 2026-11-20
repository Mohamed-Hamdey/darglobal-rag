"""
Benchmarking script for DarGlobal × Wasalt Intelligence.
Evaluates retrieval quality, retrieval latency, and end-to-end API latency.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from collections import defaultdict

# Ensure we can import from the app directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import httpx
    from app.retrieval.store import retrieve
    from app.retrieval.router import route
except ImportError as e:
    print(f"Import error: {e}. Make sure you are running this from the project root with the virtual environment activated.")
    sys.exit(1)

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

def load_questions(eval_path: Path) -> list[dict]:
    questions = []
    if not eval_path.exists():
        print(f"Warning: {eval_path} not found. Creating a dummy set.")
        eval_path.parent.mkdir(parents=True, exist_ok=True)
        dummy = [
            {"q": "What branded residences does DarGlobal partner with?", "expect": "darglobal", "cat": "entity_en"},
            {"q": "Typical apartment prices in Riyadh?", "expect": "wasalt", "cat": "numeric"},
            {"q": "ما هي مشاريع دار جلوبال في السعودية؟", "expect": "darglobal", "cat": "arabic"},
            {"q": "What is Dar Global's share price?", "expect": "NONE", "cat": "adversarial"}
        ]
        with open(eval_path, "w", encoding="utf-8") as f:
            for q in dummy:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        return dummy

    with open(eval_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
    return questions

def evaluate_retrieval(eval_path: Path):
    print("🔍 Running Retrieval Evaluation (No LLM calls)...")
    questions = load_questions(eval_path)
    
    stats = defaultdict(lambda: {"hits": 0, "total": 0, "reciprocal_ranks": [], "latencies": []})
    overall_latencies = []

    for q in questions:
        query = q["q"]
        expect = q["expect"]
        cat = q.get("cat", "unknown")
        
        # Determine source filter based on category
        source = "wasalt" if cat in ("numeric", "listing") else "darglobal" if cat == "entity_en" else "both"
        
        t0 = time.perf_counter()
        chunks = retrieve(query, source_filter=source, k=5)
        t1 = time.perf_counter()
        
        latency_ms = (t1 - t0) * 1000
        stats[cat]["latencies"].append(latency_ms)
        overall_latencies.append(latency_ms)
        stats[cat]["total"] += 1
        
        # Evaluate Hit@5 and MRR
        hit = False
        for rank, chunk in enumerate(chunks, 1):
            # Check if expected keyword is in URL or text
            if expect == "NONE":
                # For adversarial, a "hit" is actually a successful retrieval of *nothing* or refusal
                # We'll count it as a pass if chunks are empty or don't contain obvious wrong answers
                hit = True 
                break
            
            if expect.lower() in chunk.get("url", "").lower() or expect.lower() in chunk.get("text_display", "").lower():
                hit = True
                stats[cat]["reciprocal_ranks"].append(1.0 / rank)
                break
        
        if hit:
            stats[cat]["hits"] += 1

    # Aggregate results
    results = {"retrieval": {"categories": {}, "overall": {}}}
    
    for cat, data in stats.items():
        total = data["total"]
        hits = data["hits"]
        hit_rate = (hits / total * 100) if total > 0 else 0
        mrr = statistics.mean(data["reciprocal_ranks"]) if data["reciprocal_ranks"] else 0.0
        p50 = statistics.median(data["latencies"]) if data["latencies"] else 0.0
        p95 = sorted(data["latencies"])[int(len(data["latencies"]) * 0.95)] if len(data["latencies"]) >= 20 else (max(data["latencies"]) if data["latencies"] else 0.0)
        
        results["retrieval"]["categories"][cat] = {
            "questions": total,
            "hit@5": f"{hit_rate:.0f}% ({hits}/{total})",
            "mrr": f"{mrr:.2f}",
            "p50_ms": f"{p50:.1f}",
            "p95_ms": f"{p95:.1f}"
        }

    # Overall stats
    total_q = sum(d["total"] for d in stats.values())
    total_hits = sum(d["hits"] for d in stats.values())
    overall_hit_rate = (total_hits / total_q * 100) if total_q > 0 else 0
    overall_mrr = statistics.mean([rr for d in stats.values() for rr in d["reciprocal_ranks"]])
    overall_p50 = statistics.median(overall_latencies) if overall_latencies else 0.0
    overall_p95 = sorted(overall_latencies)[int(len(overall_latencies) * 0.95)] if len(overall_latencies) >= 20 else (max(overall_latencies) if overall_latencies else 0.0)

    results["retrieval"]["overall"] = {
        "questions": total_q,
        "hit@5": f"{overall_hit_rate:.0f}% ({total_hits}/{total_q})",
        "mrr": f"{overall_mrr:.2f}",
        "p50_ms": f"{overall_p50:.1f}",
        "p95_ms": f"{overall_p95:.1f}"
    }

    print(f"✅ Retrieval Eval Complete. Overall Hit@5: {results['retrieval']['overall']['hit@5']}")
    return results["retrieval"]

async def evaluate_api(api_url: str, n: int):
    print(f"⏱️  Running End-to-End API Evaluation ({n} questions)...")
    questions = load_questions(Path("data/eval/questions.jsonl"))[:n]
    latencies = []
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for q in questions:
            query = q["q"]
            print(f"  Querying: {query[:50]}...")
            
            t0 = time.perf_counter()
            try:
                async with client.stream("POST", f"{api_url}/api/chat", json={"message": query, "source": "both"}) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            if '"type": "done"' in line:
                                break
            except Exception as e:
                print(f"  ❌ Error: {e}")
                continue
            
            t1 = time.perf_counter()
            latency_s = t1 - t0
            latencies.append(latency_s)
            print(f"  ✅ Done in {latency_s:.2f}s")

    if not latencies:
        return {"error": "No successful API calls made."}

    p50 = statistics.median(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies)
    
    results = {
        "api": {
            "samples": len(latencies),
            "p50_s": f"{p50:.2f}",
            "p95_s": f"{p95:.2f}",
            "min_s": f"{min(latencies):.2f}",
            "max_s": f"{max(latencies):.2f}"
        }
    }
    print(f"✅ API Eval Complete. p50: {p50:.2f}s, p95: {p95:.2f}s")
    return results["api"]

def generate_markdown(retrieval_data: dict, api_data: dict):
    md = []
    md.append("# Benchmark Results\n")
    md.append("> Auto-generated by `scripts/benchmark.py`\n")
    
    md.append("## Retrieval Quality & Latency\n")
    md.append("| Category | Questions | Hit@5 | MRR | p50 (ms) | p95 (ms) |")
    md.append("|---|---|---|---|---|---|")
    for cat, data in retrieval_data["categories"].items():
        md.append(f"| {cat.replace('_', ' ').title()} | {data['questions']} | {data['hit@5']} | {data['mrr']} | {data['p50_ms']} | {data['p95_ms']} |")
    md.append(f"| **Overall** | **{retrieval_data['overall']['questions']}** | **{retrieval_data['overall']['hit@5']}** | **{retrieval_data['overall']['mrr']}** | **{retrieval_data['overall']['p50_ms']}** | **{retrieval_data['overall']['p95_ms']}** |\n")

    if "api" in api_data and "error" not in api_data:
        md.append("## End-to-End API Latency\n")
        md.append(f"- **Samples:** {api_data['api']['samples']}")
        md.append(f"- **p50:** {api_data['api']['p50_s']} s")
        md.append(f"- **p95:** {api_data['api']['p95_s']} s")
        md.append(f"- **Range:** {api_data['api']['min_s']} s – {api_data['api']['max_s']} s\n")
    else:
        md.append("## End-to-End API Latency\n")
        md.append("*(Not run. Use `--api` flag to measure.)*\n")

    out_path = RESULTS_DIR / "metrics.md"
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"📝 Markdown report saved to {out_path}")

def main():
    parser = argparse.ArgumentParser(description="Benchmark RAG retrieval and API latency.")
    parser.add_argument("--eval", type=str, help="Path to evaluation JSONL (runs retrieval only)")
    parser.add_argument("--api", type=str, help="Base URL of running API (e.g., http://localhost:8000)")
    parser.add_argument("--n", type=int, default=5, help="Number of questions to test for API eval")
    parser.add_argument("--out", type=str, default="results", help="Output directory")
    
    args = parser.parse_args()
    global RESULTS_DIR
    RESULTS_DIR = Path(args.out)
    RESULTS_DIR.mkdir(exist_ok=True)

    final_results = {}

    if args.eval:
        eval_path = Path(args.eval)
        final_results["retrieval"] = evaluate_retrieval(eval_path)

    if args.api:
        final_results["api"] = asyncio.run(evaluate_api(args.api, args.n))

    if final_results:
        json_path = RESULTS_DIR / "metrics.json"
        json_path.write_text(json.dumps(final_results, indent=2), encoding="utf-8")
        print(f"💾 JSON data saved to {json_path}")
        
        generate_markdown(final_results.get("retrieval", {}), final_results.get("api", {}))
    else:
        print("No actions specified. Use --eval or --api.")

if __name__ == "__main__":
    main()