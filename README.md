# Deneme-002

Bu depo, Streamlit tabanlı "Akıllı Veri Analizcisi" uygulamasını içerir.

## Başlangıç

1. Depoyu klonlayın:
   ```bash
   git clone https://github.com/<kullanici-adiniz>/Deneme-002.git
   cd Deneme-002
   ```

   > **Önemli:** Yukarıdaki URL örnektir. `git clone` komutunu yazarken `https://github.com/<kullanici-adiniz>/Deneme-002.git`
   > kısmındaki `<kullanici-adiniz>` bölümünü kendi GitHub kullanıcı adınızla değiştirin. PowerShell'de `<` ve `>`
   > karakterlerini aynen yazmak komutun çalışmamasına neden olur ("The '<' operator is reserved" hatası).
2. Gerekli paketleri kurun (önerilen sanal ortam içerisinde):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows PowerShell
   # source .venv/bin/activate  # macOS / Linux
   pip install -r requirements.txt
   ```

   > **İpucu:** Komutu çalıştırmadan önce terminalinizin `requirements.txt` dosyasının
   > bulunduğu depo dizininde (`Deneme-002`) olduğundan emin olun. Örneğin Windows
   > PowerShell kullanıyorsanız `ls` yazdığınızda dosya listesinde `requirements.txt` görünmelidir.
   > Eğer görünmüyorsa `cd C:\AI_Program\Deneme-002` komutuyla klasöre geçin, aksi hâlde
   > "Could not open requirements file" hatası alırsınız.
3. Uygulamayı başlatın:
   ```bash
   streamlit run app.py
   ```

> **Not:** Eğer `git pull` veya başka bir Git komutunu çalıştırırken "fatal: not a git repository" hatası alırsanız, komutu
> bir Git deposu içinde çalıştırdığınızdan emin olun. `Deneme-002` klasörünün içinde `.git` klasörü görünmüyorsa depo
> henüz klonlanmamış demektir. Bu durumda komut satırında `git status` yazarak nerede olduğunuzu kontrol edin; gerekirse
> `git clone ...` adımını tekrarlayın veya `git init` ile yeni bir depo başlatın.

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

