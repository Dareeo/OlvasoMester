# OlvasóMester

**Verzió:** 1.3 | **Build:** 2026.04.09 | **Platform:** Windows

Magyar szövegfelolvasó, amely automatikusan felolvassa a vágólap tartalmát.

---

## Funkciók

- **Automatikus vágólap-figyelés** – amint szöveget másolsz, azonnal elkezdi felolvasni
- **Magyar hangok** – három minőségi Piper TTS hang: Anna, Berta, Imre
- **Szavanként kiemelés** – olvasás közben a szövegben kiemeli az éppen felolvasott szót
- **Állítható sebesség** – 50–200% között szabadon állítható a felolvasás üteme
- **Rendszertálca ikon** – a háttérben fut, a tálcán keresztül érhető el
- **Automatikus frissítés** – opcionálisan ellenőrzi és letölti az új verziókat
- **Ablak pozíció mentése** – a következő indításkor ugyanott nyílik meg az ablak
- **Automatikus bezárás** – beállítható, hogy felolvasás után mennyi idővel záródjon be az ablak

---

## Rendszerkövetelmények

- Windows 10/11
- [Piper TTS](https://github.com/rhasspy/piper) futtatható (a program könyvtárában: `piper/piper.exe`)
- Magyar Piper modellek a `piper/models/` mappában:
  - `hu_HU-anna-medium.onnx`
  - `hu_HU-berta-medium.onnx`
  - `hu_HU-imre-medium.onnx`

### Python függőségek (forrásból futtatáshoz)

```
pip install pyperclip pystray Pillow numpy sounddevice
```

---

## Telepítés és indítás

### Előre lefordított verzió (.exe)
Töltsd le a legújabb kiadást a [hivatalos weboldalról](https://olvasomester.dareeo.hu), csomagold ki, és futtasd az `olvasomester.exe` fájlt.

### Forrásból
```bash
git clone https://github.com/Dareeo/OlvasoMester.git
cd OlvasoMester
pip install pyperclip pystray Pillow numpy sounddevice
python olvasomester.py
```
> A Piper TTS motornak és a magyar modelleknek a `piper/` almappában kell lenniük.

---

## Használat

1. Indítsd el az alkalmazást – a tálcán megjelenik az ikon
2. Másolj bármilyen magyar szöveget a vágólapra (Ctrl+C)
3. Az OlvasóMester automatikusan megnyitja a felolvasó ablakot és felolvassa a szöveget
4. A felolvasás bármikor megszakítható az ablak bezárásával

### Beállítások (tálca ikon → Beállítások)

| Beállítás | Leírás |
|---|---|
| Felolvasás sebessége | 50–200% (alapértelmezett: 100%) |
| Felolvasó hangja | Anna / Berta / Imre |
| Automatikus bezárás | 0–60 másodperc (0 = ki) |
| Automatikus frissítés | Új verzió automatikus ellenőrzése |

---

## Technikai részletek

- **TTS motor:** [Piper](https://github.com/rhasspy/piper) – offline, helyi feldolgozás
- **Párhuzamos generálás:** a szöveg chunkokra osztva párhuzamosan kerül generálásra, így folyamatos a lejátszás
- **Beállítások tárolása:** Windows registry (`HKCU\Software\OlvasoMester`)
- **Felhasznált könyvtárak:** tkinter, pystray, sounddevice, numpy, Pillow, pyperclip

---

## Szerző

**D@reeo**
- Web: [olvasomester.dareeo.hu](https://olvasomester.dareeo.hu)
- Email: dareeo@gmail.com

---

## Licenc

Személyes és oktatási célra szabadon használható.
