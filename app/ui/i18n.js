const I18N = {
  en: {
    eyebrow: "Bespoke Real Estate Research",
    hero1: "Inquire into",
    hero_sub: "Branded residences, architectural developments, market valuations, and auction listings — synthesized directly from verified records.",
    st_pages: "Pages Indexed",
    st_wa: "Wasalt Listings",
    st_src: "Data Feeds",
    st_date: "Dataset Snapshot",
    src_both: "Both",
    src_dar: "DarGlobal",
    src_wa: "Wasalt",
    new_chat: "New Inquiry",
    source_detail: "Source Reference",
    theme_to_light: "Switch to daylight theme",
    theme_to_dark: "Switch to obsidian theme",
    offline: "Connection lost — waiting to reconnect…",
    ph: "Ask about residences, pricing, or market listings…",
    foot1: "Unofficial technical showcase · Informational only · Figures reflect collected dataset, not live market quotes.",
    sources: "Citations",
    assistant: "Intelligence",
    cached: "Cached",
    sources_only: "Sources only",
    copy: "Copy",
    copied: "Copied",
    regen: "Regenerate",
    stopped: "Response stopped.",
    waking: "Initializing Engine",
    waking_txt: "The server is waking from standby. First inquiry may take up to a minute.",
    err_title: "Inquiry Interrupted",
    err_txt: "The assistant could not complete this request.",
    retry: "Retry Inquiry",
    open: "Open Original Source",
    no_excerpt: "Click below to view the full original record directly on the source portal.",
    starters: [
      { cat: "Residences", q: "What branded residences does DarGlobal partner with?" },
      { cat: "Valuations", q: "Typical apartment prices in Riyadh?" },
      { cat: "Alliances", q: "Which luxury brands partner with DarGlobal?" },
      { cat: "Spotlight", q: "Tell me about Trump Tower Jeddah" },
      { cat: "Market Data", q: "How do Wasalt listings break down by city?" },
      { cat: "العربية", q: "ما هي مشاريع دار جلوبال في السعودية؟", ar: true }
    ],
    followups: {
      both: [
        "Compare DarGlobal luxury developments vs. Wasalt market averages",
        "Which cities have the highest concentration of listings?",
        "Show key specifications and starting prices"
      ],
      darglobal: [
        "Which luxury fashion and automotive brands partner with DarGlobal?",
        "Compare Trump Tower Jeddah with other Saudi projects",
        "What international destinations does DarGlobal develop in?"
      ],
      wasalt: [
        "Break down Wasalt listings by property type and city",
        "What are the price ranges for villas vs. apartments?",
        "Are there active auction listings in Riyadh or Jeddah?"
      ]
    },
    partners: "Trump Organization · Aston Martin · Automobili Lamborghini · Pagani · FENDI Casa · Marriott · W Hotels · Paramount · Missoni · Elie Saab · Mouawad"
  },
  ar: {
    eyebrow: "أبحاث العقارات الفاخرة",
    hero1: "استكشف",
    hero_sub: "مساكن بعلامات عالمية، مشاريع معمارية، تقييمات سوقية، ومزادات عقارية — إجابات موثّقة مباشرة من المصادر.",
    st_pages: "صفحات مفهرسة",
    st_wa: "عقارات وسالت",
    st_src: "مصادر البيانات",
    st_date: "تاريخ البيانات",
    src_both: "الكل",
    src_dar: "دار جلوبال",
    src_wa: "وسالت",
    new_chat: "استفسار جديد",
    source_detail: "مرجع المصدر",
    theme_to_light: "التبديل إلى الوضع النهاري",
    theme_to_dark: "التبديل إلى الوضع الليلي",
    offline: "انقطع الاتصال — بانتظار عودة الشبكة…",
    ph: "اسأل عن المشاريع، الأسعار، أو العقارات المدرجة…",
    foot1: "عرض تقني غير رسمي · للمعلومات فقط · الأرقام تعكس مجموعة البيانات المسجلة وليست أسعار سوق حية.",
    sources: "المصادر",
    assistant: "المساعد الذكي",
    cached: "مخزّن مؤقتاً",
    sources_only: "المصادر فقط",
    copy: "نسخ",
    copied: "تم النسخ",
    regen: "إعادة التوليد",
    stopped: "تم إيقاف الإجابة.",
    waking: "جارٍ تهيئة النظام",
    waking_txt: "الخادم في وضع الاستعداد. قد يستغرق الاستفسار الأول دقيقة واحدة.",
    err_title: "تعذّر إتمام الطلب",
    err_txt: "لم يتمكن المساعد من إكمال هذا الاستفسار.",
    retry: "إعادة المحاولة",
    open: "فتح المصدر الأصلي",
    no_excerpt: "اضغط أدناه للاطلاع على السجل الأصلي الكامل مباشرة عبر بوابة المصدر.",
    starters: [
      { cat: "مساكن فاخرة", q: "ما هي مساكن العلامات الفاخرة التي تتعاون معها دار جلوبال؟" },
      { cat: "تقييمات", q: "ما متوسط أسعار الشقق في الرياض؟" },
      { cat: "شراكات", q: "ما هي العلامات التجارية الشريكة مع دار جلوبال؟" },
      { cat: "مشروع مميز", q: "أخبرني عن برج ترامب جدة" },
      { cat: "بيانات السوق", q: "كيف تتوزع عقارات وسالت حسب المدينة؟" },
      { cat: "English", q: "What branded residences does DarGlobal partner with?" }
    ],
    followups: {
      both: [
        "قارن بين مشاريع دار جلوبال الفاخرة ومتوسط أسعار وسالت",
        "ما هي المدن الأكثر توفراً للعقارات المدرجة؟",
        "اعرض أبرز المواصفات والأسعار الابتدائية"
      ],
      darglobal: [
        "ما هي علامات الأزياء والسيارات الفاخرة الشريكة مع دار جلوبال؟",
        "قارن برج ترامب جدة مع المشاريع الأخرى في السعودية",
        "ما هي الوجهات الدولية التي تطور فيها دار جلوبال؟"
      ],
      wasalt: [
        "صنّف عقارات وسالت حسب نوع العقار والمدينة",
        "ما هي نطاقات أسعار الفلل مقارنة بالشقق؟",
        "هل توجد مزادات عقارية نشطة في الرياض أو جدة؟"
      ]
    },
    partners: "ترامب أورغانيزيشن · أستون مارتن · لامبورغيني · باغاني · فندي كازا · ماريوت · دبليو هوتلز · باراماونت · ميزوني · إيلي صعب · معوّض"
  }
};

function applyI18n(lang = (typeof state !== "undefined" ? state.lang : "en")) {
  const t = I18N[lang] || I18N.en;
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";

  document.querySelectorAll("[data-i18n]").forEach(el => {
    const k = el.dataset.i18n;
    if (t[k]) el.textContent = t[k];
  });
  document.querySelectorAll("[data-i18n-ph]").forEach(el => {
    const k = el.dataset.i18nPh;
    if (t[k]) el.placeholder = t[k];
  });

  if (typeof syncThemeButton === "function") syncThemeButton();

  const mq = document.getElementById("mqtext");
  if (mq) mq.textContent = (t.partners + "   ·   ").repeat(3);
  renderStarters(lang);
}

function renderStarters(lang = "en") {
  const t = I18N[lang] || I18N.en;
  const box = document.getElementById("starters");
  if (!box) return;
  box.innerHTML = "";

  t.starters.forEach((s, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "starter";
    b.dataset.q = s.q;
    if (s.ar) b.dir = "rtl";
    b.innerHTML = `
      <span class="st-top"><b>${String(i + 1).padStart(2, "0")}</b> · ${s.cat}</span>
      <span class="st-q">${s.q}</span>
      <span class="st-arrow">
        <svg width="15" height="15" viewBox="0 0 16 16">
          <path d="M2 8h11M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.4"/>
        </svg>
      </span>`;
    box.appendChild(b);
  });
}