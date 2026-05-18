"""
Münazara — Demo Verisi

app.py'den ayrıştırıldı. UI katmanında hardcode'dan kurtulmak için.
"""

DEMO_TOPIC = "Türev nedir"

DEMO_MESSAGES = [
    {
        "role": "professor",
        "content": (
            "Türev, bir fonksiyonun belirli bir noktadaki anlık değişim hızıdır. "
            "Arabayı düşünün: hız göstergesi size o anki türevi gösteriyor — "
            "ne kadar hızlı değiştiğinizi. Peki siz bana söyleyin: araba sabit "
            "hızda gidiyorsa, hızın türevi ne olur?"
        ),
    },
    {
        "role": "student",
        "content": (
            "Hocam yani türev hız mı? Ben sanıyordum bir şeylerin mesafesini "
            "hesaplıyordu. Sabit hızda türev... sıfır mı olur?"
        ),
    },
    {
        "role": "professor",
        "content": (
            "Yaklaştınız ama tam değil, Kamil. Türev mesafe değil, değişim hızıdır. "
            "Hız sabitken sıfır olan türev değil — ivmedir, yani hızın türevi sıfırdır. "
            "Her türev sorusunda 'neyin türevi' diye sormak zorundasınız. "
            "Peki pozisyonun türevi nedir?"
        ),
    },
    {
        "role": "student",
        "content": (
            "Aa yani her şeyin türevi ayrı mı? Pozisyonun türevi hız mı oluyor o zaman? "
            "Peki hızın türevi de ivme mi — zincir gibi mi gidiyor bu?"
        ),
    },
    {
        "role": "professor",
        "content": (
            "İşte şimdi konuşuyoruz! Buna türev zinciri diyebiliriz: konum → hız → ivme. "
            "Newton bu bağlantıyı keşfetmeden önce kimse bu tabloyu görmemişti. "
            "Şimdi size bir soru: ivmenin de türevi var mıdır, "
            "ve fiziksel anlamı ne olabilir?"
        ),
    },
    {
        "role": "student",
        "content": (
            "İvmenin türevi... jerk mi? Bir yerde duymuştum. "
            "Arabanın aniden frene basması gibi bir şey mi? "
            "Ama hocam bütün bunlar nasıl hesaplanıyor — sezgisel anladım "
            "ama formül kısmı hâlâ muğlak."
        ),
    },
    {
        "role": "professor",
        "content": (
            "Evet, jerk — Türkçesiyle sarsıntı. Mühendisler onu da ölçer. "
            "Formül kısmına gelince: f'(x) = lim[h→0] (f(x+h) - f(x)) / h. "
            "Bu bir limit tanımıdır. Sizi şuraya çekeyim: bu formülde h sıfıra "
            "yaklaşırken ne olduğunu düşünün — neden tam sıfır yapmıyoruz?"
        ),
    },
]