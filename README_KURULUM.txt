╔══════════════════════════════════════════════════════╗
║          ProScore Analytics - Kurulum Kılavuzu      ║
╚══════════════════════════════════════════════════════╝

──────────────────────────────────────────────────────
 GEREKSİNİMLER
──────────────────────────────────────────────────────
• Windows 10 veya Windows 11
• Python 3.10 veya üzeri
  İndirmek için: https://www.python.org/downloads/
  ÖNEMLİ: Kurulum sırasında "Add Python to PATH"
           seçeneğini mutlaka işaretleyin!
• İnternet bağlantısı (ilk kurulum için)

──────────────────────────────────────────────────────
 KURULUM (tek seferlik)
──────────────────────────────────────────────────────
1. Bu klasörü istediğiniz bir yere kopyalayın
   (örn: C:\ProScore veya masaüstünüze)

2. "install.bat" dosyasına çift tıklayın

3. Kurulum tamamlandığında masaüstünüzde
   "ProScore Analytics" kısayolu oluşturulur

──────────────────────────────────────────────────────
 KULLANIM
──────────────────────────────────────────────────────
• Masaüstündeki "ProScore Analytics" kısayoluna
  çift tıklayın

• Uygulama otomatik olarak tarayıcınızda açılır
  (http://localhost:8501)

• Kapatmak için: siyah komut pencerelerini kapatın

──────────────────────────────────────────────────────
 API ANAHTARLARI (opsiyonel, daha iyi veri için)
──────────────────────────────────────────────────────
Uygulama API anahtarı olmadan NBA ve bazı futbol
ligleri için çalışır. Daha kapsamlı veri için:

1. .env dosyasını bir metin editörü ile açın
2. API anahtarlarınızı girin:
   ODDS_API_KEY=buraya_yazin

──────────────────────────────────────────────────────
 SORUN GİDERME
──────────────────────────────────────────────────────
• "Python bulunamadı" hatası:
  → Python'u yükleyin ve "Add to PATH" seçin

• Tarayıcı açılmıyor:
  → Manuel olarak açın: http://localhost:8501

• Uygulama başlamıyor:
  → launch.bat'ı sağ tık → Yönetici olarak çalıştır

• Kaldırmak için:
  → uninstall.bat dosyasına çift tıklayın
