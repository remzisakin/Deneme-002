# Deneme-002

Bu depo, Streamlit tabanlı "Akıllı Veri Analizcisi" uygulamasını içerir.

## Başlangıç

1. Depoyu klonlayın:
   ```bash
   git clone <repo-url>
   cd Deneme-002
   ```
2. Gerekli paketleri kurun (önerilen sanal ortam içerisinde):
   ```bash
   pip install -r requirements.txt
   ```

   > **İpucu:** Komutu çalıştırmadan önce terminalinizin `requirements.txt` dosyasının
   > bulunduğu depo dizininde (`Deneme-002`) olduğundan emin olun. Örneğin Windows
   > PowerShell kullanıyorsanız önce `cd C:\AI_Program\Deneme-002` komutunu çalıştırın;
   > aksi hâlde `requirements.txt` bulunamadı hatası alırsınız.
3. Uygulamayı başlatın:
   ```bash
   streamlit run app.py
   ```

> **Not:** Eğer `git pull` komutunu çalıştırırken "fatal: not a git repository" hatası alırsanız, komutu bir Git deposu içinde çalıştırdığınızdan emin olun. Örneğin, `Deneme-002` klasörünün içinde `.git` klasörü bulunmalıdır. Eğer yoksa depoyu yeniden klonlayın veya `git init` ile yeni bir depo başlatın.

## Çevresel Değişkenler

Uygulamanın LLM özelliğini kullanmak için `.env` dosyasına aşağıdaki değeri ekleyin:

```bash
OPENAI_API_KEY=<api-anahtarınız>
```

## Faydalı Komutlar

- Kod stilini kontrol edin:
  ```bash
  black --check app.py
  ```
- Uygulamayı yerel olarak test edin:
  ```bash
  streamlit run app.py
  ```

