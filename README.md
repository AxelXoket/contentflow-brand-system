# ContentFlow: Harcama Takip Paneli marka içerik sistemi

[Harcama Takip Paneli](https://axelxoket.github.io/expense-tracker-dashboard/) için hazırladığım marka ve içerik seti:
marka analizi, marka sesi, 7 günlük içerik takvimi, blog, üç sosyal medya gönderisi, üç görsel, iki Instagram hikâyesi,
panelin gerçek ekran kaydıyla dikey tanıtım videosu, seslendirme ve yayın öncesi kontrol listesi. Bütün dosyalar `brand/`
ve `content/` altındaki kaynaklardan tek komutla üretilir; bir metin marka sesi kurallarına uymazsa derleme hiçbir dosya
yazmadan durur.

Panelin kendisi ayrı bir depoda: [expense-tracker-dashboard](https://github.com/AxelXoket/expense-tracker-dashboard).

## Teslim dosyaları

Hepsi `deliverables/` altında. Teslimin kendisi oldukları için depoda bilerek tutuluyorlar.

| Dosya | İçerik | Aşama |
| --- | --- | --- |
| `marka-stratejisi.pdf` | 2 sayfa: ürün ve sektör, 5 rakibin kaynaklı karşılaştırması (App Store Türkiye fiyatları, TL), pazardaki boşluk, renk paleti, değerler, görsel dil, Neden-Kime-Ne-Nasıl, persona, ton ve kelimeler, 4 içerik sütunu, ölçüm | 1 ve 2 |
| `marka-sesi-rehberi.pdf` | 1 sayfa: yapın ve yapmayın, kelimeler, örnekler, duruma göre ton, yazım kuralları, kanala göre ses, çağrı | 2 |
| `icerik-takvimi.xlsx` | 7 gün (23-29 Kasım 2026): tarih, gün, saat, kanal, format, konu, sütun, amaç, çağrı, gerekçe, dosya, durum | 3 |
| `icerik-seti/blog.pdf`, `blog.html` | SEO uyumlu blog yazısı, iki panel görseli; HTML'de açıklama, Open Graph ve Article etiketleri | 3 |
| `icerik-seti/gorsel-*.png` | Marka paletinde üç görsel, 1080x1080, alt metinleriyle | 3 |
| `icerik-seti/hikaye-anket.png` | Cumartesi anket hikâyesi, 1080x1920 | 3 |
| `icerik-seti/hikaye-pazar.mp4` | Pazar sesli hikâyesi: seslendirme, adımlar ve ilerleme çubuğu, 1080x1920 | 3 |
| `icerik-seti/tanitim-videosu.mp4` | Dikey tanıtım videosu, 1080x1920, 16,4 saniye; ekleme ve ayın resmi sahneleri panelin gerçek ekran kaydı | 3 |
| `icerik-seti/video-kareleri/` | Videonun beş sahnesinden birer kare | 3 |
| `icerik-seti/seslendirme.mp3` | Pazar günü için TTS seslendirme, 24,2 saniye; cümleler arası 0,6 saniye | 3 |
| `ekran-goruntuleri/` | 11 ekran görüntüsü, 2560x1440: kimlik kartı, takvim, gerekçeler, blog, üç gönderi, görseller, hikâyeler, video ve ses, istemler | 4 |
| `kontrol-listesi.pdf` | 2 sayfa: her parça için marka sesi, sayı, ürün iddiası, telif ve etik sonucu; her iddianın kaynak dosyası ve satırı | 4 |
| `sunum.pdf` | 23 slaytlık 16:9 sunum; yapay zekâ kullanımı 21. slaytta; video, ses ve kaynak bağlantıları tıklanır | Hepsi |
| `sunum-slaytlar/` | Her slaytın 2560x1440 PNG kopyası | Hepsi |

Sosyal medya metinleri ve RTF istemleri sunumun 14-16. slaytlarında ve `content/social.json` içinde. Görsel, video ve
ses istemleri 20. slaytta ve `content/media.json` içinde. Blogun CO-STAR istemi `content/prompts.json` içinde.

Video ve ses tarayıcıda oynar: [tanitim-videosu.mp4](https://axelxoket.github.io/contentflow-brand-system/deliverables/icerik-seti/tanitim-videosu.mp4), [hikaye-pazar.mp4](https://axelxoket.github.io/contentflow-brand-system/deliverables/icerik-seti/hikaye-pazar.mp4), [seslendirme.mp3](https://axelxoket.github.io/contentflow-brand-system/deliverables/icerik-seti/seslendirme.mp3).

Canva: slayt PNG'leri görsel olarak yüklenirse görünüm aynen kalır. `sunum.pdf` "PDF içe aktar" ile de açılır, ama Canva'da
Segoe UI olmadığı için yazılar başka yazı tipine geçip satır değiştirebilir. Video ve ses dosyaları Canva'ya ayrıca
yüklenir.

## Nasıl üretilir

Gerekenler: Windows, Python 3.14, Microsoft Edge (sayfaları başsız açıp PNG ve PDF'e çevirir), ffmpeg ve ffprobe 8.1,
seslendirme için internet bağlantısı (edge-tts Microsoft'un çevrimiçi sesini kullanır).

```bash
python -m pip install -r requirements.txt
```

```bash
python tools/build.py
```

Tek bir parça için adını verin: `images`, `voice`, `stories`, `video`, `calendar` ya da `docs`. `stories` seslendirmeyi,
`docs` görselleri ve video karelerini kullandığı için onlardan sonra çalışır.

```bash
python tools/build.py images docs
```

`panel` adımı canlı paneli başsız Edge'de açar (Playwright): örnek verilerle bir harcama ekler, her adımın karesini ve
eklemeden sonraki sayfayı `assets/video/` altına, masaüstü görünümünü `assets/panel-2x.png` olarak kaydeder. İnternet
istediği ve çıktılar kayıtlı karelerden üretildiği için yalnız adı verilince çalışır.

```bash
python tools/build.py panel
```

Derleme sırası:

1. `tools/checks.py` yayımlanan her metni denetler (blog, gönderiler, görsel ve hikâye yazıları, alt metinler, video ve
   ses metinleri, takvim). Bir sorun varsa derleme listeyi yazıp durur.
2. Her sayfa HTML olarak kurulur ve başsız Edge'de açılır. Sayfadaki betik her yazının kaç satıra yayıldığını ve bir şeyin
   kutusundan taşıp taşmadığını ölçer. Bir yazı izin verilen satırı aşarsa ya da taşarsa dosya yazılmaz.
3. Videonun her cümlesi ayrı seslendirilir, sessizliği kesilir ve cümleler 0,25 saniye arayla birleşir; seslendirmede bu
   ara 0,6 saniyedir. Kareler Pillow ile çizilir: yazı belirerek gelir, metin sahneleri yavaşça yaklaşır, form sahnesinde
   tutar harf harf yazılır, ayın resmi sahnesinde sayfa bütçeden kategori dağılımına kayar. Ses yüksekliği -14 LUFS
   hedefiyle ayarlanır; üç dosyada ölçülen değer -15,0 ile -15,1 LUFS. Video 15-20 saniye, seslendirme 20-30 saniye
   dışında kalırsa eski dosyalar yerinde kalır ve derleme durur.
4. Sunum PDF'e basılır, sonra her sayfası PyMuPDF ile `sunum-slaytlar/` altına PNG olarak çıkarılır.
5. Edge hiçbir pencere açmadan çalışır; derleme önce ve sonra görünür Edge penceresi sayısını karşılaştırır.

## Yapay zekâyı nerede ve nasıl kullandım

| Görev | Araç | Neden bu araç | Karşılaşılan risk ve önlem |
| --- | --- | --- | --- |
| Marka stratejisi, ses rehberi, takvim, blog, gönderi, görsel ve video metinleri | Claude (Claude Code), RTF ve CO-STAR istemleriyle | Uzun marka bağlamını ve kuralları bir arada tutuyor; istemler `content/` altında durduğu için her metin aynı istemle yeniden üretilebiliyor | Dil modeli kanıtsız ürün iddiası ya da marka dışı kelime üretebilir. `tools/checks.py` yayımlanan her metni denetliyor; kaynak satırına bağlanmayan bir iddia ya da kaçınılan bir kelime derlemeyi durduruyor |
| Seslendirme | edge-tts, Türkçe sinirsel ses `tr-TR-EmelNeural` | Ücretsiz, Türkçe, betikten çağrılabiliyor | Süre hedef aralığın dışına taşabilir; cümleler ayrı seslendirilip sessizlikleri kesiliyor, süre tutmazsa derleme duruyor. Microsoft bu kullanım için açık bir ticari izin vermiyor; ses yalnız bu projenin gösterimi için, reklamdan önce lisanslı bir sesle (Azure AI Speech) yeniden üretilmeli. Sesli hikâyede "Seslendirme yapay sesle üretildi." notu var |
| Görseller, hikâyeler, video kareleri | Görsel üretim modeli yok: HTML şablonları başsız Edge'de, kareler Pillow ile çiziliyor; panel ekranları gerçek uygulamadan Playwright ile alındı | Görseldeki arayüz ve sayılar gerçek ürünle aynı olmalı; uydurma bir ekran da kanıtsız bir ürün iddiasıdır | Türkçe yazılar satır sonunda bölünebilir; sayfadaki betik satırları ölçüyor, taşan dosya yazılmıyor |
| Derleme, denetim ve test kodu | Claude (Claude Code) | Metin ve onu denetleyen kod aynı oturumda birlikte değişiyor | Her kural bir davranış testiyle ve kuralı bozan mutantlarla sınanıyor (README'deki Testler bölümü) |

İstem kütüphanesi: sosyal medya istemleri `content/social.json`, görsel, video ve ses istemleri `content/media.json`, blogun
CO-STAR istemi `content/prompts.json` içinde; sunumun 14-16. ve 20. slaytlarında da görünüyor. Üretilen her metin yayından
önce yukarıdaki denetimlerden geçiyor; her parçanın sonucu kontrol listesinde.

## Denetimler

| Kural | Nerede |
| --- | --- |
| Cümle en çok 20 kelime | `checks.long_sentences` |
| Kaçınılan kelimeler ve ekli biçimleri (israfı, garantili) | `checks.avoided_words` |
| Okura "siz" denir; "sen" biçimleri yakalanır | `checks.singular_address` |
| Her sayı, yanındaki kelimeyle birlikte, ya kanıtlı bir ürün olgusu ya da "öneri" diye etiketli kendi sayımız; yazıyla yazılan sayılar da | `checks.unexplained_numbers`, `brand/brand.json` (`facts`, `own_numbers`, `forms`) |
| Her parçanın ürün iddiaları bulunur ve kaynak satırına bağlanır | `checks.claims_in`, `brand/brand.json` (`product_claims`, `phrases`) |
| Videoda ekrandaki yazı ile ses aynı kelimeler | `checks.same_words`, `build.content_problems` |
| Kanal sınırları: Instagram 2200, LinkedIn 3000, X 280 karakter; etiket sayısı; panel bağlantısı, Instagram'da "bağlantı profilde" | `checks.post_problems` |
| Blog: başlık en çok 60 karakter, açıklama 120-155, tek H1, anahtar kelime başlıkta, H1'de, ilk paragrafta, açıklamada ve bir H2'de, 600-1200 kelime, bağlantı ve uyarı | `checks.blog_problems` |
| Yazı satır sınırı, taşma, kısa çizgili kelimenin bölünmemesi, sayının birimiyle ya da para işaretiyle aynı satırda kalması, "ya da", "siz de", "var mı" gibi eklerin önceki kelimeden ayrılmaması | `render.FIT_SCRIPT`, `build.keep_together` |
| Renk çiftleri en az 4,5:1 kontrast (WCAG AA) | `checks.contrast`, `brand/brand.json` (`text_pairs`) |

Yayımlanan parçalardaki her ürün iddiası, sayılı ya da sayısız, `brand/brand.json` içinde panelin kaynak dosyası ve oradaki satırla
birlikte duruyor (örnek: Geri al düğmesi 6 saniye ekranda kalır, `UndoToast.jsx` içinde `UNDO_MS = 6000`). Hangi parçanın
hangi iddiayı taşıdığı kontrol listesinin 2. sayfasında. Rakip bilgileri üretici sayfalarından ve App Store Türkiye
listelerinden alındı; her satırın kaynağı ve erişim tarihi `brand/competitors.json` içinde.

## Testler

```bash
python -B -m unittest discover -s tests -t .
```

166 test, yaklaşık 20 saniye; Edge kullanan 11 test bunun çoğunu alıyor.

- `test_checks.py`: her kural sınırın iki yanından sınanır (20 ve 21 kelime, 280 ve 281 karakter, 119/120/155/156
  karakterlik açıklama, 599/600/1200/1201 kelime); iddia bulucu ve "bağlantı profilde" kuralı.
- `test_content.py`: gerçek içerik bütün denetimlerden geçer; takvim pazartesiden başlayan 7 ardışık gün, her satırda
  saat, her sütun kullanılmış, her parça takvimde; istemler eksiksiz ve istemdeki etiket sınırı denetimle aynı; videoda
  ekrandaki yazı ile ses aynı; her görselin ve hikâyenin alt metni var; her iddia en az bir parçada geçiyor ve kaynak
  gösterilen her satır panelin kodunda gerçekten var; panelin kodunda ağ isteği yok; her gönderinin ölçütü kanalının
  raporladığı bir sayı; README'deki yapay zekâ tablosu sunum slaytıyla aynı kaynaktan; rakip tablosunda "bulunamadı" diye bırakılmış hücre yok;
  kayıtlı panel kareleri tutarlı.
- `test_helpers.py`: yazı yardımcıları, kontrol listesi sütunları, video zamanlaması (yumuşak geçiş, form adımları, sayfa
  kayması, sahne süresi), cümle birleştirme ve seslendirmenin cümle cümle okunması, hikâye ilerleme çubuğu, video ve
  seslendirme süresi kapısı, sessizlik kesme (ffmpeg ile üretilmiş deneme sesleriyle); Pages bağlantısı, slayt PNG'leri,
  seçenekleri Instagram'a bırakan anket kartı.
- `test_render.py`: satır ve taşma ölçümü gerçek bir başsız Edge'de, her kural için bozuk ve sağlam bir sayfayla.
- `test_deliverables.py`: üretilmiş dosyalar: boyutlar, video süresi ve ses kanalı, videoda bir saniye duran kare ve
  cümleler arasında 0,6 saniyeden, seslendirmede 0,9 saniyeden uzun sessizlik olmaması, ses yüksekliği, hikâyeler, takvim
  satırları, gönderi ölçütleri, tablonun altındaki hedef notu ve yazdırma ayarı, sunumdaki yapay zekâ slaytı ve takvim
  ölçütleri, sunumdaki video, ses ve kaynak bağlantılarının depodaki dosyalara gitmesi, her slaytın PNG
  kopyası, sayfa sayıları, boş sayfa olmaması, PDF'teki her kelimenin bir kaynak dosyada geçmesi, satır sonunda bölünmüş
  kelime ya da kelimesinden ayrılmış sayı olmaması, blog sayfasının paylaşım etiketleri ve görselleri, ekran görüntüsü
  listesi.
- `test_text_hygiene.py`: depodaki her metin dosyasında uzun tire, yasaklı üslup kelimesi ve CRLF yok; araç adları yalnız README'nin yapay zekâ bölümünde ve sunumdaki yapay zekâ slaytının verisinde (`content/ai_usage.json`) geçer.

Testlerin gerçekten bir şey yakaladığını görmek için kuralları tek tek bozan 95 mutasyon denendi; hepsi en az bir
testi kırmızıya çevirdi. Mutasyonlar projenin geçici bir kopyasında koşar:

```bash
python -B tools/mutation_check.py
```

## Klasörler

```
brand/        marka verisi: kimlik, palet, ses, persona, sütunlar, olgular ve iddialar; rakipler ve kaynakları
content/      yayımlanan metinler: blog, gönderiler, görsel, hikâye ve video metinleri, takvim, kontrol notları, istemler
assets/       panelin örnek verilerle alınmış ekran görüntüsü ve video kareleri (assets/video/)
tools/        checks.py (denetimler), render.py (Edge), panel.py (canlı panel), build.py (görsel, ses, hikâye, video,
              takvim), docs.py (PDF'ler, sunum)
tests/        davranış testleri
deliverables/ üretilmiş teslim dosyaları
```

## Bilinen sınırlar

- Yazıyla yazılan sayılar ("beş dakika", "yüzde seksen") rakama çevrilip denetlenir. "bir" ve "yedi" çevrilmez, çünkü
  metinde çoğu zaman "bir harcama" ve "yedi (yemek)" anlamındadır. "on", "altı", "yüz" yalnız tek başına bir kelimeyken
  sayıdır; "online", "altında" gibi kelimeler etkilenmez.
- Sıra sayısı noktası ("1.") yalnız başlık ya da liste satırının başında kabul edilir. Cümle içindeki "ayın 15. günü" gibi
  bir kullanım denetime takılır; o biçimin `own_numbers` içine eklenmesi gerekir.
- Blog yazısının yayın adresi belli değil; `blog.html` bu yüzden canonical ve `og:url` taşımaz, `og:image` da göreli yoldur; adres belli olunca mutlak
  adresler eklenir.
- Edge yolu Windows'a göre yazıldı (`tools/render.py`, `EDGE`).
- Ses Microsoft Edge'in çevrimiçi sesli okuma hizmetiyle (edge-tts) üretildi. Microsoft bu kullanım için açık bir ticari
  izin vermiyor; bu yüzden ses yalnız bu projenin gösterimi içindir, reklamda kullanılmadan önce lisanslı bir sesle (Azure AI
  Speech, aynı ses `tr-TR-EmelNeural`) yeniden üretilmeli. Sesli hikâyede "Seslendirme yapay sesle üretildi." notu var.
- İçerik genel bilgi verir; finansal ya da yatırım tavsiyesi değildir.
