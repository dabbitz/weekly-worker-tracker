# WorkTrack — Haftalık İş Takip Sistemi

WorkTrack; ofis ve şantiye ekipleri için Türkçe öncelikli bir haftalık iş takip sistemidir. Çalışanlar için bir Telegram botunu, serbest metin güncellemelerini yapılandırılmış ilerleme kayıtlarına dönüştüren yapay zekâ destekli bir raporlama akışını, bir REST API'yi ve projeler, çalışanlar, görevler, atamalar, haftalık planlar ve yönetici raporları için Türkçe bir yönetici panelini bir araya getirir.

Tüm uygulama verileri PostgreSQL (Neon) üzerinde tutulur. Telegram botu, FastAPI arka ucu ve React paneli aynı veritabanını ve iş mantığı katmanını paylaşan ayrı süreçlerdir.

> "Bu hafta elektrik tesisatının yaklaşık %70'ini tamamladık. Ancak kablo tedarikinde sorun yaşadığımız için kalan kısmı bitiremedik. Malzemeler yarın gelirse cuma gününe kadar bitirmeyi planlıyoruz."
>
> ↓ ↓ ↓

```json
{
  "task_reference_text": "elektrik tesisatı",
  "status": "blocked",
  "completion_percentage": 70,
  "blocker": "kablo tedarikinde sorun",
  "delay_reason": null,
  "next_step": "malzemeler geldiğinde kalan işi bitirmek",
  "reported_eta_text": "cuma gününe kadar",
  "summary": "Elektrik tesisatının %70'i tamamlandı. Kablo tedarik sorunu nedeniyle kalan kısım bitirilemedi. Malzemeler yarın gelirse cuma gününe kadar tamamlanması planlanıyor."
}
```

---

## Özellikler

### Telegram ve iş raporları

- **Onaylı çalışan kaydı** — çalışan ad soyad ve isteğe bağlı pozisyon bilgisi gönderir; yapılandırılmış Telegram yöneticisi talebi onaylamadan hiçbir çalışan kaydı aktif hâle gelmez.
- **İsteğe bağlı pozisyon** — pozisyon kayıt sırasında sorulur, `/atla` ile geçilebilir ve daha sonra panelden düzenlenebilir. Bu bir görev/unvan etiketidir, yetkilendirme rolü değildir.
- **Göreve bağlı raporlama** — çalışanlar `/gorevlerim` (veya `/rapor`) komutuyla kendilerine atanan görevleri görür ve seçtikleri görev için rapor gönderir.
- **Doğal dilden bilgi çıkarımı** — Gemini, Türkçe veya İngilizce serbest metni Pydantic ile doğrulanan bir `WorkUpdate` şemasına dönüştürür.
- **Doğal dilden ilerleme tahmini** — açıkça belirtilen yüzdeler aynen korunur; "yarısını tamamladık" gibi ifadeler savunulabilir bir yaklaşık yüzdeye çevrilir, belirsiz mesajlar için yüzde uydurulmaz.
- **Gecikme ile engel ayrımı** — devam eden ancak geciken iş "devam ediyor" durumunda kalır ve ayrı bir `delay_reason` kaydedilir. `blocked` yalnızca belirtilen engel işin sürmesini gerçekten durduruyorsa kullanılır.
- **Kaydetmeden önce önizleme** — çalışan çıkarılan alanları görür, düzenleyebilir ve ancak açıkça onayladığında kayıt oluşturulur.
- **Tarihsel kayıtlar** — onaylanan her rapor yeni bir `task_updates` satırıdır. Önceki raporların üzerine yazılmaz.
- **Tekrarlı kayıt koruması** — bir Telegram mesajı yalnızca bir rapor oluşturabilir.
- **İstem enjeksiyonuna dayanıklı** — mesajlar yalnızca veri olarak işlenir; model hiçbir zaman veritabanı kimliği üretmez.

### Yönetici paneli

- **Güvenli tek yönetici girişi** — Argon2 parola özeti ve imzalı, süresi dolan JWT erişim belirteçleri.
- **Genel Bakış** — gerçek proje, aktif çalışan, görev ve bekleyen kayıt talebi sayıları; son projeler ve bilinçli boş durumlar.
- **Proje yönetimi** — konum ve beklenen tamamlanma tarihiyle proje oluşturma, arama, düzenleme, görüntüleme ve silme.
- **Proje detayı** — proje bilgileri, projenin görevleri ve görev atamalarından türetilen ekip.
- **Çalışan yönetimi** — çalışanları listeleme/arama, atanmış görevleri ve türetilen projeleri inceleme, pozisyonu düzenleme ve geçmiş raporları bağlı değilse çalışanı silme.
- **Görev yönetimi** — proje içinde görev oluşturma ve düzenleme, planlanan başlangıç/bitiş tarihlerini belirleme ve bir veya daha fazla çalışan atama.
- **Haftalık planlama** — yapay zekâ ile üretilen veya elle hazırlanan haftalık hedefler; onaylama, reddetme, değiştirme ve geçmiş takibi.
- **Kayıt geçmişi** — bekleyen, onaylanan ve reddedilen Telegram kayıt taleplerini inceleme. Kararlar Telegram'da verilir.
- **Raporlar** — çalışan iş raporlarını inceleme ve yapay zekâ destekli haftalık yönetici raporları oluşturma.
- **Yalnızca gerçek veri** — örnek/demo kayıt veya uydurma metrik yoktur.

### Yapay zekâ ile haftalık planlama

- Bir veya daha fazla görev seçip isteğe bağlı talimat ekleyerek çok haftalık taslak hedefler üretilir.
- Pazartesi başlangıçlı haftalar görevin gerçek planlanan tarihlerine göre kırpılır.
- Hedefler haftalık artış değil, hafta sonunda beklenen kümülatif tamamlanma yüzdesidir.
- Yapay zekâ çıktısı, yönetici onaylayana kadar her zaman taslaktır.
- Görev/hafta başına yalnızca bir onaylı plan bulunabilir; değiştirildiğinde önceki plan `superseded` olarak korunur.

### Haftalık yönetici raporları

- Pazartesi–pazar haftası için elle başlatılan yönetici raporları; zamanlayıcı veya arka plan işçisi yoktur.
- Belirleyici metrikler saf SQL/Python ile hesaplanır; Gemini yalnızca bu sayıları yorumlar.
- Doğrulama; uydurulmuş sayı, tarih, belirteç, sınıflandırma, çalışan adı ve kimlik bilgilerini reddeder.
- Rapor sürümleri hafta bazında saklanır, başarısız üretimler yeniden denenebilir ve kaynak verilere dokunmadan rapor belgesi silinebilir.
- Yönetici müdahale önerileri, belirleyici kural adayları ile kaynaklara dayalı yapay zekâ önerilerini birleştirir.

---

## Nasıl Çalışır?

```mermaid
flowchart LR
    E[Çalışan] -->|/register veya /gorevlerim| B[aiogram botu]
    B -->|Yapay zekâ taslağı| G[Google Gemini]
    G -->|Doğrulanmış WorkUpdate| B
    B -->|Çalışanın onayladığı rapor| DB[(PostgreSQL / Neon)]
    A[Yönetici] --> D[React paneli]
    D -->|REST + JWT| API[FastAPI arka ucu]
    API --> DB
    API -->|Plan taslakları ve rapor anlatısı| G
```

### Çalışan kaydı

1. Çalışan özel sohbette `/register İsim Soyisim` komutunu gönderir.
2. Bot isteğe bağlı pozisyon bilgisini sorar. Çalışan `/atla` yazabilir veya bu alanı yönetici daha sonra doldurabilir.
3. `registration_requests` satırı oluşturulur ve yöneticiye Telegram üzerinden onay/red butonları gönderilir.
4. Yalnızca onay, yeni bir çalışan oluşturur veya mevcut çalışanı yeniden aktifleştirir. Başvuru sahibine karar bildirilir.

### İş raporu akışı

1. Çalışan `/gorevlerim` veya `/rapor` komutunu gönderir.
2. Bot, aktif çalışana atanmış görevleri ve varsa bugünü kapsayan onaylı haftalık hedefi listeler.
3. Çalışan bir görev seçer ve raporunu serbest metin olarak yazar.
4. Gemini yapılandırılmış alanları çıkarır.
5. Bot; hedef ile bildirilen ilerlemeyi ayrı etiketlerle, ayrıca engel, gecikme, sonraki adım ve tahmini bitiş bilgileriyle birlikte önizler.
6. Çalışan tek tek alanları düzenleyebilir, iptal edebilir veya onaylayabilir.
7. Yalnızca onay, `task_updates` tablosuna yeni bir satır ekler. Mesajın aslı, yapay zekâ modeli ve normalize edilmiş tahmini bitiş tarihi de saklanır.

### Haftalık yönetici raporu

1. Yönetici **Raporlar → Haftalık Yönetici Raporları** bölümünde bir hafta seçer.
2. Arka uç; planları, raporları, sınıflandırmaları, çakışmaları ve müdahale adaylarını içeren belirleyici bir metrik özeti oluşturur.
3. Gemini anlatıyı yalnızca anonim belirteçler ve doğrulanmış gerçekler üzerinden yazar.
4. Anlatı doğrulanır ve o hafta için numaralı bir sürüm olarak saklanır.
5. Panel; proje, çalışan ve görev analizlerini, geçmiş hafta karşılaştırmasını, veri kalitesi notlarını ve yönetici müdahalelerini gösterir.

---

## Teknoloji Yığını

| Katman | Teknoloji |
| --- | --- |
| Bot çatısı | [aiogram 3](https://aiogram.dev/) |
| Yapay zekâ | `google-genai` üzerinden [Google Gemini](https://ai.google.dev/) |
| Arka uç API | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| Doğrulama | [Pydantic v2](https://docs.pydantic.dev/) |
| ORM | [SQLAlchemy 2.0 (async)](https://www.sqlalchemy.org/) |
| Veritabanı | PostgreSQL (Neon) + `asyncpg` |
| Veritabanı geçişleri | Alembic |
| Kimlik doğrulama | Argon2 (`argon2-cffi`) + PyJWT |
| Ön uç | React 19 + TypeScript + Vite |
| Arayüz ve stil | Tailwind CSS, erişilebilir yerel bileşenler, `lucide-react` ikonları |
| Yönlendirme | React Router |
| Sunucu durumu | TanStack Query |
| Ön uç denetimi | oxlint |
| Yapılandırma | `python-dotenv` |

---

## Proje Yapısı

```text
weekly-work-tracker/
├── app/
│   ├── api/
│   │   ├── main.py              # FastAPI giriş noktası (Telegram botu değil)
│   │   ├── config.py            # Panel ortam ayarları
│   │   ├── security.py          # JWT üretimi/doğrulaması ve iptal
│   │   ├── dependencies.py      # Bearer kimlik doğrulama ve DB oturumu
│   │   ├── errors.py            # API hata yönetimi
│   │   └── routes/              # Kimlik, panel, proje, çalışan, görev,
│   │                            # plan, kayıt talebi, rapor rotaları
│   ├── bot/
│   │   ├── handlers.py          # /gorevlerim, önizleme, düzenleme, onay akışları
│   │   ├── states.py            # Kayıt ve raporlama FSM durumları
│   │   ├── drafts.py            # Taslak doğrulama ve alan düzenlemeleri
│   │   ├── selection.py         # Görev/plan anlık görüntü yardımcıları
│   │   └── formatting.py        # Türkçe Telegram mesajları ve klavyeleri
│   ├── database/
│   │   ├── connection.py        # Asenkron motor ve oturum fabrikası
│   │   ├── models.py            # SQLAlchemy ORM modelleri
│   │   └── repositories.py      # Ortak veri erişim yardımcıları
│   ├── schemas/                 # Pydantic API ve yapay zekâ sözleşmeleri
│   └── services/                # İş mantığı, yapay zekâ servisleri, metrikler, doğrulama
├── alembic/
│   └── versions/                # Şema geçişleri (0001–0004)
├── frontend/
│   ├── src/
│   │   ├── api/                 # REST istemcisi ve uç nokta fonksiyonları
│   │   ├── components/          # Arayüz ve özellik bileşenleri
│   │   ├── hooks/               # Kimlik doğrulama bağlamı
│   │   ├── layouts/             # Kenar çubuğu/başlık uygulama kabuğu
│   │   ├── pages/               # Panel sayfaları
│   │   ├── types/               # Paylaşılan TypeScript veri tipleri
│   │   └── App.tsx              # Yönlendirici ve sağlayıcılar
│   └── package.json
├── tests/                       # Otomatik arka uç testleri
├── scripts/
│   └── hash_admin_password.py   # Argon2 parola özeti yardımcısı
├── alembic.ini
├── init_db.py                   # Yalnızca sıfırdan kurulum; Alembic tercih edilir
├── main.py                      # Telegram botu giriş noktası
├── requirements.txt
├── pytest.ini
├── .env                         # Yerel gizli değerler (commit edilmez)
└── .env.example                 # Yalnızca yer tutucular
```

---

## Başlarken

### Gereksinimler

- Python **3.11+**
- Node.js **20+** ve npm
- [@BotFather](https://t.me/BotFather) üzerinden alınmış Telegram bot belirteci
- [Google AI Studio](https://aistudio.google.com/apikey) üzerinden alınmış Google Gemini API anahtarı
- Bir PostgreSQL veritabanı (ücretsiz bir [Neon](https://neon.tech/) projesi yeterlidir)

### 1. Depoyu klonlayın

```bash
git clone https://github.com/dabbitz/weekly-worker-tracker.git
cd weekly-worker-tracker
```

### 2. Sanal ortam oluşturun

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Bağımlılıkları yükleyin

```bash
pip install -r requirements.txt
```

### 4. Ortam değişkenlerini yapılandırın

Proje kökünde `.env` dosyası oluşturun:

```env
# Telegram
BOT_TOKEN=your-telegram-bot-token
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.5-flash-lite

# PostgreSQL (Neon)
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
DATABASE_URL_POOLED=postgresql://user:password@host/dbname?sslmode=require

# Telegram yöneticisi (kayıt onayı; panel girişi değildir)
ADMIN_TELEGRAM_ID=123456789

# Yönetici paneli
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=replace-with-an-argon2-hash
AUTH_SECRET=replace-with-at-least-32-random-characters
ACCESS_TOKEN_EXPIRE_MINUTES=480
# FRONTEND_ORIGIN=https://your-dashboard.example.com

# İsteğe bağlı ön uç derleme değeri (asla gizli bilgi değildir)
# VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

Notlar:

- `GEMINI_MODEL` isteğe bağlıdır ve varsayılan değeri `gemini-3.5-flash-lite`'tır.
- Panel parola özetini, düz metin parolayı bir dosyaya yazmadan üretin:

  ```bash
  python scripts/hash_admin_password.py
  ```

  Yazdırılan Argon2 özetini `ADMIN_PASSWORD_HASH` alanına kopyalayın.
- `AUTH_SECRET` en az 32 karakter olmalıdır.
- `ADMIN_TELEGRAM_ID` ile `ADMIN_USERNAME` farklı kanalların kimlik doğrulamasıdır ve ayrı tutulmalıdır.

### 5. Veritabanı geçişlerini uygulayın

```bash
# Windows
.\.venv\Scripts\python.exe -m alembic upgrade head

# macOS / Linux
.venv/bin/python -m alembic upgrade head
```

Paneli veya botu kullanmadan önce geçişleri uygulayın. `init_db.py` sıfırdan kurulum için bulunur, ancak `Base.metadata.create_all()` kullandığı için mevcut tabloları değiştiremez; şema değişikliklerinde desteklenen yol Alembic'tir.

### 6. Telegram botunu çalıştırın

```bash
python main.py
```

Telegram'da botu açın ve `/start` gönderin.

### 7. Yönetici API'sini çalıştırın

```bash
# Windows (PowerShell)
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --port 8000

# macOS / Linux
.venv/bin/python -m uvicorn app.api.main:app --reload --port 8000
```

API `http://127.0.0.1:8000` adresinde, etkileşimli dokümanlar `http://127.0.0.1:8000/docs` adresinde ve sağlık kontrolü `http://127.0.0.1:8000/api/health` adresinde çalışır.

### 8. Ön ucu çalıştırın

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173` adresini açın ve yapılandırılmış `ADMIN_USERNAME` ile parolayı kullanarak giriş yapın. Ön uç, varsayılanı `http://127.0.0.1:8000/api` olan `VITE_API_BASE_URL` değerini okur. Bu yalnızca herkese açık bir derleme değeridir; `VITE_*` değişkenlerine asla gizli bilgi koymayın.

Bot, API ve ön uç üç ayrı süreç olarak çalışır.

---

## Telegram Botu

| Komut | Açıklama |
| --- | --- |
| `/start` | Karşılama mesajı ve temel kullanım yönlendirmesi |
| `/help` | Kullanılabilir komutları listeler |
| `/myid` | Kullanıcının Telegram kullanıcı kimliğini gösterir |
| `/register İsim Soyisim` | Onaylı kayıt talebi başlatır |
| `/gorevlerim` | Atanmış görevleri listeler ve iş raporu akışını başlatır |
| `/rapor` | `/gorevlerim` ile aynı işlevi görür |

Yalnızca metin raporları desteklenir. Ses, ses dosyası ve video notu gönderimlerinde sesli raporlamanın henüz etkin olmadığını açıklayan bir mesaj gönderilir.

### Kayıt ve onay

- Kayıt yalnızca özel sohbette yapılabilir.
- Ad ve soyad zorunludur; pozisyon isteğe bağlıdır.
- Pozisyon sorusu `/atla` (veya `/geç`, `-`, `yok`) ile geçilebilir.
- Telegram hesabı başına yalnızca bir bekleyen talep bulunabilir. Reddedilen başvuru sahibi yeniden başvurabilir.
- Yönetici; talep numarası, ad soyad, pozisyon, Telegram kimliği ve kullanıcı adını görür ve **Onayla** / **Reddet** butonlarını kullanır.
- Yönetici kimliği `ADMIN_TELEGRAM_ID` ile doğrulanır; yalnızca buton verisine güvenilmez.
- Onay, çalışanı oluşturur veya yeniden aktifleştirir ve başvuru sahibine bildirim gönderir.
- Panel kayıt taleplerini görüntüleyip silebilir; ancak onaylama/reddetme yapmaz. Bu kararlar Telegram'da verilir.

### Rapor akışı

- Yalnızca Telegram hesabı bağlı ve aktif olan çalışanlar rapor gönderebilir.
- Rapor, çalışana atanmış bir göreve bağlı olmalıdır.
- Bot; rapor gönderilirken çalışanı, görev atamasını ve haftalık planı veritabanından yeniden çözer.
- Taslak alanları önizleme gösterilmeden önce sınırlandırılır ve doğrulanır.
- Düzenleme işlemi onay belirtecini yeniler; böylece eski buton yeni bir taslağı onaylayamaz.
- Önizleme ile onay arasında haftalık plan değişirse eski önizleme kaydedilmez.
- Onaylanan rapor `review_status = approved` olarak saklanır; bu, çalışanın yapay zekâ taslağını onayladığı anlamına gelir, yönetici incelemesi değildir.
- Raporların üzerine yazılmaz; her mesaj bağımsız bir tarihsel kayıttır.
- Görev ataması bulunmayan veya aktif olmayan çalışanlar için kayıt oluşturulmaz.

### İş durumu değerleri

| Değer | Anlamı |
| --- | --- |
| `completed` | Bildirilen işin tamamı bitmiştir |
| `in_progress` | İş devam etmektedir ve sürebilir |
| `blocked` | Belirtilen bir engel nedeniyle iş devam edememektedir |
| `not_started` | Çalışan işe başlanmadığını açıkça söylemiştir |
| `unknown` | Durumu belirlemek için yeterli bilgi yoktur |

### Gecikme ve engel ayrımı

| Durum | Saklanan bilgi |
| --- | --- |
| Belirtilen bir engel işi durdurmuştur | `status = blocked` ve `blocker` |
| İş devam ediyor ancak takvim gecikiyor | çalışma durumu (genellikle `in_progress`) ve `delay_reason` |
| Hem engel hem gecikme bildirilmiştir | hem `blocker` hem `delay_reason` |
| Tamamlanan işte geçmiş bir gecikmeden söz edilmiştir | `status = completed` |

Tek başına bir gecikme, durumu asla `blocked` yapmaz. Tamamlanmış bir iş de gecikme nedeniyle geriye düşürülmez.

### İlerleme yüzdesi tahmini

- Açıkça belirtilen yüzde aynen kullanılır.
- Sayı verilmemiş ancak mesaj genel ilerlemeyi açıkça anlatıyorsa yaklaşık bir değer çıkarılabilir:

| İfade | Çıkarılan ilerleme |
| --- | --- |
| "Daha yeni başladık." | 10 |
| "Yarısını tamamladık." | 50 |
| "Çoğu bitti." | 75 |
| "Neredeyse tamamladık." | 90 |
| "İşin tamamını bitirdik." | 100 |

- Belirsiz bir mesaj `null` üretir; varsayılan bir yüzde uydurulmaz.
- "Bu hafta" gibi bir zaman ifadesi, yüzdeyi haftalık ilerlemeye dönüştürmez.
- Değerler her zaman 0 ile 100 arasında kalır.

### Tahmini bitiş tarihleri

- Tahmini bitiş ifadesinin aslı `reported_eta_text` alanında korunur.
- Arka uç, ifadeyi Telegram mesajının özgün zaman damgası ve `Europe/Istanbul` saat dilimini kullanarak `reported_eta_date` alanına normalize eder.
- Türkçe hafta günleri, gün/ay adları, `yarın`, `bugün`, `öbür gün`, `haftaya cuma`, göreli süreler ve yaygın sayısal tarih biçimleri desteklenir.
- Teslimat, toplantı, denetim ve benzeri etkinlik tarihleri görevin bitiş tarihi olarak kabul edilmez.
- Tarih belirsiz veya desteklenmiyorsa yalnızca özgün ifade saklanır.

---

## Yönetici Paneli

Panel, Türkçe öncelikli bir React uygulamasıdır. Yalnızca FastAPI arka ucuyla konuşur, PostgreSQL'e doğrudan bağlanmaz.

| Sayfa | Amacı |
| --- | --- |
| Genel Bakış | Gerçek proje, aktif çalışan, görev ve bekleyen kayıt sayıları; son projeler; ilk adım yönlendirmesi |
| Projeler | Proje oluşturma, arama, düzenleme ve silme; proje detayına geçiş |
| Proje Detayı | Proje bilgileri, görevler ve görev atamalarından türetilen çalışanlar |
| Çalışanlar | Çalışan arama, aktif/pasif filtreleme, çalışan detayına geçiş |
| Çalışan Detayı | Atanmış görevler, bu atamalar üzerinden türetilen projeler, pozisyon düzenleme |
| Görevler | Görev oluşturma/düzenleme, planlanan tarihleri belirleme, birden fazla çalışan atama, yapay zekâ ile haftalık planlama başlatma |
| Haftalık Planlar | Taslakları inceleme veya elle plan oluşturma; düzenleme, onaylama, reddetme, silme ve yapay zekâ notlarını görüntüleme |
| Kayıt Talepleri | Durum/arama filtreleriyle salt okunur Telegram kayıt geçmişi; kararlar Telegram'da verilir |
| Raporlar | Çalışan iş raporları ve yapay zekâ destekli haftalık yönetici raporları |

Temel davranışlar:

- Projeler henüz görev veya çalışan yokken de oluşturulabilir.
- Proje oluşturmak asla otomatik çalışan veya atama yaratmaz.
- Bir göreve `task_assignments` üzerinden birden fazla çalışan atanabilir.
- Pasif çalışanlar yeni bir göreve atanamaz.
- Proje ekipleri `tasks → task_assignments → employees` üzerinden türetilir; `project_memberships` tablosu yoktur.
- Görev ataması olmayan çalışanlar, bir projeye yapay olarak bağlanmadan genel çalışan listesinde görünür.
- Haftalık plan hedefleri, görevin planlanan başlangıç/bitiş tarihlerinden ayrıdır.
- Çalışanlar sisteme yalnızca Telegram onayıyla girer; panel kimlik bilgilerini değil pozisyonlarını düzenler.
- Proje silme, planlama verilerini kaldırır; ancak geçmiş raporlar projenin görev veya planlarına başvuruyorsa silme reddedilir.
- Çalışan silme, görev atamalarını kaldırır; ancak geçmiş raporlar o çalışana başvuruyorsa silme reddedilir.
- Yıkıcı işlemler onay ister ve silme öncesinde etkisini gösterir.

---

## Yapay Zekâ ile Haftalık Planlama

- Yönetici **Görevler** sayfasında bir veya daha fazla görev seçer, isteğe bağlı ek talimat ekler ve taslak ister.
- Gemini, kesin olarak doğrulanan çok haftalık bir plan döndürür. Her öneri `source = ai` ve `draft` durumuyla saklanır.
- Planlama haftaları pazartesi başlar, yedi gün sürer ve görevin planlanan başlangıç/bitiş tarihlerine göre kırpılır.
- `target_completion_percentage`, o haftanın sonunda beklenen **kümülatif** tamamlanmadır; haftalık artış değildir.
- Yüzdeler 0–100 arasında tam sayı olmalı ve haftadan haftaya azalmamalıdır.
- Taslak düzenlenebilir, onaylanabilir, reddedilebilir veya silinebilir. Elle oluşturulan planlar `source = manual` kullanır.
- Aynı görev/hafta için birden fazla taslak bulunabilir; ancak kısmi benzersiz indeks **görev/hafta başına yalnızca bir onaylı plana** izin verir. Çakışan bir taslağı onaylamak açık değiştirme onayı gerektirir; önceki onaylı plan silinmek yerine `superseded` olur.
- Onaylı bir plan değiştirildiğinde önceki plan `superseded` olarak korunur. Planlar, hiçbir iş raporu onlara başvurmuyorsa açıkça silinebilir; bir rapor tarafından referans verilen plan, o rapor silinene kadar korunur.
- Üretim istekleri `request_id` ve içerik parmak izi ile idempotenttir; başarısız bir isteğin yeniden denenmesi kopya oluşturmaz.
- Yapay zekâ gerekçesi, varsayımları ve uyarıları yönetici incelemesi için her taslakla birlikte saklanır.

### Haftalık plan yaşam döngüsü

| Durum | Anlamı |
| --- | --- |
| `draft` | Düzenlenebilir öneri; henüz resmî değil |
| `approved` | O görev/hafta için tek aktif plan |
| `rejected` | İncelenip reddedildi; geçmiş için korunur |
| `superseded` | Daha yeni bir onaylı planla değiştirildi; geçmiş için korunur |

---

## Haftalık Yönetici Raporları

- **Raporlar → Haftalık Yönetici Raporları** bölümü, pazartesi–pazar haftası için saklanan bir yönetim raporu oluşturur. Üretim her zaman elle başlatılır; zamanlayıcı veya arka plan işçisi yoktur.
- Üretimden önce önizleme; proje kapsamını, görev ve rapor sayılarını, durum sayılarını, atanmamış görevleri, plan çakışmalarını, eksik hedef yüzdelerini ve müdahale adaylarını gösterir.
- Tüm sayılar `app/services/weekly_report_metrics.py` içindeki belirleyici motordan gelir. Gemini yalnızca bu sayıları yorumlar; belirleyici özette bulunmayan bir sayı, tarih, belirteç veya sınıflandırma eklerse doğrulama tarafından reddedilir.
- `target_completion_percentage` (haftalık hedef) ile `completion_percentage` (çalışanın bildirdiği ilerleme) asla aynı değer olarak sunulmaz. Farklı çalışanların yüzdeleri asla ortalanmaz ve proje düzeyinde ilerleme yüzdesi hesaplanmaz.
- Faaliyet metriklerine yalnızca `approved` iş raporları girer. `pending` raporlar faaliyet dışında tutulur ve ayrıca sayılır; `rejected` raporlar hariç tutulur.
- Eksik raporlar tarafsız biçimde (“Rapor gönderilmedi”) ifade edilir; rapor, bildirilmeyen bir görevin yapılmadığını asla söylemez.
- Haftalar `Europe/Istanbul` pazartesi–pazar sınırlarını kullanır. Varsayılan, son tamamlanan haftadır; içinde bulunulan hafta “Kısmi değerlendirme” etiketiyle üretilebilir, gelecek haftalar reddedilir.
- Rapor dönemleri `TaskUpdate.received_at` (veritabanına eklenme zamanı) üzerinden seçilir. Telegram mesajının zaman damgası ayrı bir sütunda saklanmadığı için gece yarısına yakın gönderilen bir rapor, özgün mesajdan farklı bir hafta sınırına düşebilir. Bu sınırlama, saklanan `metrics_snapshot.methodology` içinde belgelenir ve raporun hesaplama açıklamasında gösterilir.
- Gemini yükü belirteçler (`E#`, `T#`, `P#`, `U#`, `W#`, `WEEK#`) ve ayrı bir genel `ai_references` haritası içerir. Çalışan adları, Telegram kullanıcı/sohbet/mesaj kimlikleri, veritabanı kimlikleri, özgün mesajlar veya gizli bilgiler asla gönderilmez. Serbest metin alanları ayrıca bilinen çalışan adlarından arındırılır. Gerçek kimlikler ve özet etiketleri saklanan `references` sütununda kalır ve yalnızca kimliği doğrulanmış panele döndürülür; Gemini'ye asla gönderilmez.
- Büyük haftalar, istem bütçesine uyulması için proje düzeyinde bir eşleme adımı ve ardından bir sentez adımıyla işlenir.
- Rapor; genel özet, proje ve çalışan analizleri, görev değerlendirmeleri, gerçekleşmeyen iş analizi, önceki haftalarla karşılaştırma, öneriler, veri kalitesi notları ve kaynaklara dayalı yönetici müdahaleleri içerir. Öncelikler yapay zekâ önerisidir; nihai karar yöneticinindir.
- `request_id` benzersizdir. Aynı içerikle tekrarlanırsa Gemini çağrılmadan mevcut rapor döndürülür; farklı içerikle kullanılırsa `409` döner. Yeni bir `request_id` yeni sürüm oluşturur ve eski sürümleri korur. Başarısız sürümler yerinde yeniden denenebilir.
- Geçmiş görünümü, sürümleri durum filtreleriyle listeler; rapor belgelerini açma, yeniden deneme ve silme işlemlerini destekler.
- `weekly_manager_reports` tablosunun kaynak tablolara yabancı anahtarı yoktur; bu nedenle bir görev veya çalışanın silinmesi saklanan rapor geçmişini bozamaz. Bir raporun silinmesi yalnızca o rapor belgesini kaldırır.
- Tablo `alembic/versions/0003_weekly_manager_reports.py` tarafından eklenir. Yalnızca ekleme yapar ve özellik bir veritabanında kullanılmadan önce normal geçiş iş akışıyla uygulanmalıdır.

---

## REST API

Aşağıdaki tüm uç noktalar `/api` altında sunulur. `POST /auth/login` ve `GET /health` dışındaki her uç nokta bearer belirteci gerektirir.

| Alan | Uç noktalar |
| --- | --- |
| Kimlik doğrulama | `POST /auth/login`, `GET /auth/me`, `POST /auth/logout` |
| Sağlık | `GET /health` |
| Panel | `GET /dashboard/summary` |
| Projeler | `GET /projects`, `GET /projects/options`, `POST /projects`, `GET /projects/{id}`, `PATCH /projects/{id}`, `DELETE /projects/{id}`, `GET /projects/{id}/tasks`, `GET /projects/{id}/employees`, `GET /projects/{id}/deletion-preview` |
| Çalışanlar | `GET /employees`, `GET /employees/{id}`, `PATCH /employees/{id}`, `DELETE /employees/{id}` |
| Görevler | `GET /tasks`, `POST /tasks`, `GET /tasks/{id}`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}`, `PUT /tasks/{id}/assignments` |
| Haftalık planlar | `GET /weekly-plans`, `POST /weekly-plans`, `POST /weekly-plans/ai/generate`, `GET /weekly-plans/{id}`, `PATCH /weekly-plans/{id}`, `POST /weekly-plans/{id}/approve`, `POST /weekly-plans/{id}/reject`, `DELETE /weekly-plans/{id}` |
| Kayıt talepleri | `GET /registration-requests`, `GET /registration-requests/{id}`, `DELETE /registration-requests/{id}` |
| İş raporları | `GET /reports`, `GET /reports/{id}`, `DELETE /reports/{id}` |
| Haftalık yönetici raporları | `GET /weekly-reports/periods`, `GET /weekly-reports/preview`, `GET /weekly-reports`, `POST /weekly-reports`, `GET /weekly-reports/{id}`, `POST /weekly-reports/{id}/retry`, `DELETE /weekly-reports/{id}` |

Liste uç noktaları sayfalama (`page`, `page_size`) kullanır ve ilgili yerlerde arama veya filtre desteği sunar. Veritabanı erişimi her zaman FastAPI üzerinden yapılır.

---

## Veri Modeli

```mermaid
erDiagram
    EMPLOYEES ||--o{ TASK_ASSIGNMENTS : has
    TASKS ||--o{ TASK_ASSIGNMENTS : assigned_to
    PROJECTS ||--o{ TASKS : contains
    TASKS ||--o{ WEEKLY_TASK_PLANS : planned_in
    WEEKLY_PLAN_GENERATIONS ||--o{ WEEKLY_TASK_PLANS : produces
    TASKS ||--o{ TASK_UPDATES : receives
    WEEKLY_TASK_PLANS ||--o{ TASK_UPDATES : contextualizes
    EMPLOYEES ||--o{ TASK_UPDATES : submits
    EMPLOYEES ||--o{ REGISTRATION_REQUESTS : applies
```

| Tablo | Amacı |
| --- | --- |
| `employees` | İsteğe bağlı Telegram kullanıcı kimliği ve isteğe bağlı pozisyonla çalışanlar |
| `registration_requests` | Durum ve talep edilen pozisyonla Telegram kayıt geçmişi |
| `projects` | Açıklama, konum ve beklenen tamamlanma tarihiyle projeler |
| `tasks` | Bir projeye ait, planlanan tarihleri ve üretilen hafta günü sütunları olan görevler |
| `task_assignments` | Görevler ile çalışanlar arasındaki çoktan çoğa bağlantı |
| `weekly_task_plans` | Yaşam döngüsü durumu, kaynağı ve yapay zekâ notlarıyla görev başına haftalık hedefler |
| `weekly_plan_generations` | Ürettiği taslakları gruplayan tek bir yapay zekâ üretim isteği |
| `task_updates` | Onaylanmış iş raporları, çıkarılan alanlar, inceleme durumu ve eşitleme durumu |
| `weekly_manager_reports` | Metrik anlık görüntüleri, referanslar ve anlatılar içeren kendi kendine yeterli haftalık yönetici raporu belgeleri |

`task_updates.review_status`, çalışanın yapay zekâ taslağını onayladığını kaydeder. Rapor kaydedildiğinde saklanan değer `approved` olur; `pending` ve `rejected` değerleri şemada bulunur ancak panelde bir onay iş akışı olarak kullanılmaz. `sync_status`, ileride dış sistem eşitlemesi için ayrılmıştır.

---

## Testler

### Otomatik arka uç testleri

```bash
# Windows (PowerShell)
.\.venv\Scripts\python.exe -m pytest tests -q

# macOS / Linux
.venv/bin/python -m pytest tests -q
```

Test paketi, yapılandırılmış Neon veritabanı üzerinde rastgele adlandırılmış ve izole edilmiş PostgreSQL şemalarında çalışır ve sonrasında bu şemaları kaldırır. `public` şemasındaki satırları değiştirmez.

Kapsanan alanlar arasında panel kimlik doğrulaması, proje/çalışan/görev CRUD işlemleri, görev atamaları, pasif çalışan atama kuralları, haftalık planlar, yapay zekâ ile haftalık planlama, Telegram kayıt ve rapor akışları, iş güncellemesi çıkarımı, tarih normalizasyonu, haftalık yönetici raporu metrikleri, doğrulama ve haftalık rapor API'si bulunur.

### Elle duman testleri

```bash
# Veritabanı bağlantısını doğrular
python test_db.py

# Örnek bir mesaj için tek bir yapay zekâ çıkarımı çalıştırır
python test_ai.py

# Türkçe tahmini bitiş tarihi normalizasyonunu dener
python test_date_normalizer.py
```

Üç betik de yapılandırmayı `.env` dosyasından yükler ve çıkmadan önce bağlantılarını kapatır.

### Ön uç kontrolleri

```bash
cd frontend
npm run build
npm run lint
```

---

## Güvenlik Notları

- `.env` git tarafından yok sayılır — **gerçek belirteçleri veya veritabanı kimlik bilgilerini asla commit etmeyin**.
- Yapay zekâ sistem talimatı, çalışan mesajlarındaki ve yönetici notlarındaki istem enjeksiyonu girişimlerini açıkça reddeder.
- Veritabanı kimlikleri her zaman arka uç tarafından üretilir; modelden kimlik üretmesi istenmez.
- Veritabanı bağlantılarında SSL varsayılan olarak etkindir.
- Panel yalnızca Argon2 parola özeti saklar ve `AUTH_SECRET` ile kısa ömürlü JWT imzalar.
- Panel belirteçleri `sessionStorage` içinde tutulur ve çıkış işlemi belirteç kimliğini iptal eder.
- CORS, yerel Vite adresleri ve isteğe bağlı yapılandırılmış ön uç adresiyle sınırlıdır; kimlik bilgisiyle joker kaynak kullanılmaz.
- Panel gizli değerleri yalnızca arka uç ortam değişkenleridir ve `VITE_*` değişkenlerinde asla yer almaz.
- Haftalık yönetici raporu yükleri anonim belirteçler kullanır; gerçek kimlikler ve çalışan adları Gemini'ye asla gönderilmez.
- Kayıt kararı uygulanmadan önce Telegram buton verisi her zaman `ADMIN_TELEGRAM_ID` ile doğrulanır.

---

## Katkıda Bulunma

1. Depoyu çatallayın (fork).
2. Bir özellik dalı oluşturun: `git checkout -b feature/my-feature`.
3. Değişikliklerinizi işleyin: `git commit -m "Add my feature"`.
4. Dalı gönderin: `git push origin feature/my-feature`.
5. Bir çekme isteği (pull request) açın.

---

## Lisans

Henüz bir lisans belirtilmemiştir. Bu projeyi üretimde kullanmadan veya yeniden dağıtmadan önce depo sahibiyle iletişime geçin.
