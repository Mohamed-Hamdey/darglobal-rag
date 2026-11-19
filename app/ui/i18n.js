const I18N = {
  en: {
    eyebrow:"AI Research Assistant", hero1:"Ask about",
    hero_sub:"Projects, branded residences, listings, prices and auctions — answered from the sources, with citations.",
    st_pages:"Pages indexed", st_wa:"Wasalt listings", st_src:"Sources", st_date:"Data as of",
    stat_note:"Figures reflect the collected dataset, not live market data.",
    src_both:"Both", src_dar:"DarGlobal", src_wa:"Wasalt",
    ph:"Ask a question…", hint:"Enter to send · Shift+Enter for a new line",
    foot1:"Unofficial demo for a technical assessment · Informational only, not an offer · Prices and specifications are indicative and may change.",
    sources:"Sources", assistant:"Assistant", cached:"Cached", sources_only:"Sources only",
    unverified:"Figures unverified", waking:"Waking up",
    waking_txt:"The free host was asleep. This takes up to a minute on the first visit.",
    err_title:"Something went wrong", err_txt:"The assistant could not complete the request.",
    retry:"Retry", open:"Open original",
    starters:[
      {cat:"Projects", q:"What branded residences does DarGlobal partner with?"},
      {cat:"Pricing", q:"Typical apartment prices in Riyadh?"},
      {cat:"Brands", q:"Which brands partner with DarGlobal?"},
      {cat:"Project detail", q:"Tell me about Trump Tower Jeddah"},
      {cat:"Auctions", q:"How do Wasalt listings break down by city?"},
      {cat:"عربي", q:"ما هي مشاريع دار جلوبال في السعودية؟", ar:true}
    ],
    partners:"Trump Organization · Aston Martin · Lamborghini · Pagani · FENDI Casa · Marriott · W Hotels · Paramount · Missoni · Elie Saab · Mouawad"
  },
  ar: {
    eyebrow:"مساعد بحث بالذكاء الاصطناعي", hero1:"اسأل عن",
    hero_sub:"مشاريع، مساكن بعلامات فاخرة، عقارات، أسعار ومزادات — إجابات من المصادر مع توثيق.",
    st_pages:"صفحات مفهرسة", st_wa:"عقارات وسالت", st_src:"مصادر", st_date:"بيانات بتاريخ",
    stat_note:"الأرقام تعكس مجموعة البيانات المجموعة وليست بيانات سوق حية.",
    src_both:"الكل", src_dar:"دار جلوبال", src_wa:"وسالت",
    ph:"اكتب سؤالك…", hint:"Enter للإرسال · Shift+Enter لسطر جديد",
    foot1:"عرض توضيحي غير رسمي لتقييم تقني · للمعلومات فقط وليس عرضاً · الأسعار والمواصفات تقديرية وقد تتغير.",
    sources:"المصادر", assistant:"المساعد", cached:"محفوظ", sources_only:"المصادر فقط",
    unverified:"أرقام غير موثّقة", waking:"جارٍ الإقلاع",
    waking_txt:"كان الخادم المجاني خاملًا. قد يستغرق أول طلب دقيقة.",
    err_title:"حدث خطأ", err_txt:"تعذّر إتمام الطلب.",
    retry:"إعادة المحاولة", open:"افتح المصدر",
    starters:[
      {cat:"مشاريع", q:"ما هي مساكن العلامات الفاخرة التي تتعاون معها دار جلوبال؟"},
      {cat:"أسعار", q:"ما متوسط أسعار الشقق في الرياض؟"},
      {cat:"علامات", q:"ما هي العلامات التجارية الشريكة مع دار جلوبال؟"},
      {cat:"تفاصيل", q:"أخبرني عن برج ترامب جدة"},
      {cat:"مزادات", q:"كيف تتوزع عقارات وسالت حسب المدينة؟"},
      {cat:"English", q:"What branded residences does DarGlobal partner with?"}
    ],
    partners:"ترامب أورغانيزيشن · أستون مارتن · لامبورغيني · باغاني · فندي كازا · ماريوت · دبليو هوتلز · باراماونت · ميزوني · إلي صعب · مواواد"
  }
};
let LANG = "en";
function applyI18n(){
  const t = I18N[LANG];
  document.documentElement.lang = LANG;
  document.documentElement.dir = LANG==="ar" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach(el=>{ const k=el.dataset.i18n; if(t[k]) el.textContent=t[k]; });
  document.querySelectorAll("[data-i18n-ph]").forEach(el=>{ const k=el.dataset.i18nPh; if(t[k]) el.placeholder=t[k]; });
  document.getElementById("mqtext").textContent = (t.partners+" \u00A0·\u00A0 ").repeat(2);
  renderStarters();
}
function renderStarters(){
  const t=I18N[LANG], box=document.getElementById("starters");
  box.innerHTML="";
  t.starters.forEach((s,i)=>{
    const b=document.createElement("button");
    b.className="starter"; b.dataset.q=s.q;
    if(s.ar) b.dir="rtl";
    b.innerHTML=`<span class="st-top"><b>${String(i+1).padStart(2,"0")}</b> · ${s.cat}</span><span class="st-q">${s.q}</span><span class="st-arrow"><svg width="16" height="16"><use href="#i-arrow"/></svg></span>`;
    box.appendChild(b);
  });
}