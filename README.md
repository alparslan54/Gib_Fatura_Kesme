📑 GİB E-Arşiv Fatura Portalı Entegrasyonu
Bu proje, Gelir İdaresi Başkanlığı (GİB) E-Arşiv Fatura portalı üzerinden otomatik fatura oluşturma, iptal etme ve görüntüleme işlemlerini gerçekleştiren uçtan uca bir sistemdir. Kullanıcılar mobil uygulama üzerinden verilerini girerken, Python tabanlı sunucu GİB servisleriyle iletişimi yönetir.

🛠 Teknik Mimari ve Teknolojiler
Frontend (Android): Java kullanılarak geliştirildi. Kullanıcı arayüzü, fatura bilgilerinin dinamik olarak alınması ve PDF önizleme süreçlerini yönetir.

Backend (Server): Python dili kullanılarak geliştirildi. GİB portalı ile haberleşme, requests kütüphanesi ve fatura kütüphanesi/modülleri ile sağlandı.

Veri Yönetimi: JSON formatında veri transferi ve session (oturum) yönetimi.

✨ Temel Özellikler
Otomatik Giriş: GİB kullanıcı bilgileriyle güvenli oturum açma.

Fatura Oluşturma: Şahıs veya firma bilgilerine göre anlık e-arşiv fatura düzenleme.

Sorgulama ve İptal: Düzenlenen faturaları listeleyebilme ve hata durumunda iptal talebi gönderme.

PDF Desteği: Oluşturulan faturaların dijital kopyalarını görüntüleme.

