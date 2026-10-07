# Linux va Windows

Pomodoro ikkita interfeys bilan keladi. Taymerning Python modeli `timer_core.py` ichida umumiy.

| Variant | Ishga tushirish | Panel |
| --- | --- | --- |
| Ubuntu 24.04, GNOME 46 | `./install.sh` | GNOME kengaytmasi yoki AppIndicators: vaqt matni |
| Windows x64 | Qt paketidagi `Pomodoro.exe` | Tizim paneli belgisi, qolgan vaqt tooltip va menyuda |
| Boshqa Linux ish stollari | Qt paketi yoki `python desktop.py` | Ish stoli qo‘llasa tizim paneli belgisi |

Ubuntu uchun GNOME varianti tavsiya etiladi. GTK/GNOME va Qt variantlarini bir vaqtda ishlatmang:
ular alohida sozlamalar saqlaydi. Qt ichida ikkinchi nusxa ochilmaydi — yorliq yana bosilsa avvalgi oyna ochiladi.

## Manbadan ishga tushirish

Python 3.12 bilan tekshirilgan:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install -r requirements-desktop.txt
python desktop.py
```

Qt oynasining yuqorisida English, Русский yoki O‘zbekcha tanlanadi. Til sozlamasi saqlanadi.

Qt variantida boshlash/pauza/davom ettirish, uzun tanaffus, ovoz, sessiyani saqlash,
30 soniyalik ogohlantirish, barcha monitorlarda tanaffus, Esc bilan chiqish va +1 daqiqa bor.
Oyna yopilganda tizim paneli mavjud bo‘lsa taymer davom etadi. Panel mavjud bo‘lmasa
yopish ilovadan chiqadi; sessiya saqlanadi. Panel menyusidagi «Dasturdan chiqish» to‘liq yopadi.
Kompyuter uxlagan yoki ilova yopiq bo‘lgan vaqt real soat bo‘yicha hisoblanadi.

Qt versiyasida ekran qulflanganda avtomatik pauza va boshqa to‘liq ekranli ilovaga qarab
tanaffusni kechiktirish hali yo‘q. GNOME kengaytmasi imkoniyatlari README’da ko‘rsatilgan.

## Paket yig‘ish

```sh
python -m pip install -r requirements-desktop.txt "pyinstaller>=6.11,<7"
python scripts/build_desktop.py
```

Natija Windows uchun `dist/windows/Pomodoro/` va ZIP, Linux uchun `dist/linux/Pomodoro/` va TAR.GZ. Butun papkani birga tarqating: `_internal` fayllari kerak.
Foydalanuvchiga Python o‘rnatish shart emas.

Windows paketi Windows’da, Linux paketi Linux’da yig‘iladi. PyInstaller boshqa OS uchun
bevosita paket yig‘maydi: [rasmiy hujjat](https://pyinstaller.org/en/stable/usage.html).
`.github/workflows/desktop.yml` GitHub Actions’da ikkala OS uchun test va paket yig‘adi.
GitHub’ga **pomodoro-ubuntu papkasining ichidagilarni repozitoriy ildizi sifatida** joylang.
Actions → Desktop builds → tugagan ish → Artifacts orqali paketni yuklab oling.

Windows’da arxivni oching, `Pomodoro.exe` ni ikki marta bosing. Desktop va Start Menu
yorlig‘i uchun shu papkada PowerShell’dan `./install-windows.ps1` ni ishlating.
U faqat foydalanuvchining LocalAppData papkasiga o‘rnatadi, administrator talab qilmaydi.
PowerShell siyosati skriptni bloklasa, `.exe` ni to‘g‘ridan-to‘g‘ri ishlatish mumkin.

Linux Qt paketida `bash install-linux.sh` foydalanuvchi hisobiga o‘rnatadi.
Linux ikkilik paketi yig‘ilgan distributiv va undan yangi mos tizimlar uchun mo‘ljallangan;
har bir distributivda ishga tushishi kafolatlanmaydi. Manbadan ishga tushirish ham mavjud.

## Tekshirish

```sh
python -m unittest discover -s tests -p desktop_test.py -v
node --test tests/timer.test.mjs
```

Qt sinovlari ekransiz backendda tugmalar, chegaralar, pauza, qayta tiklash, uzun tanaffus
va noto‘g‘ri saqlangan sessiyani tekshiradi. Windows CI natijasi va haqiqiy Windows’da
panel/ovoz/ko‘p monitor sinovi alohida kerak; Linux’dagi testlar bularni tasdiqlamaydi.

## Dizayn

- Taymer → vaqt tanlash → asosiy amal → qo‘shimcha sozlamalar tartibi.
- + va − bir xil o‘lcham, rang va shrift; ikonka mavzusidan mustaqil.
- Boshlash/Pauza/Davom ettirish bitta joyda; foydalanilmaydigan tugmalar yashirin.
- Holat matn bilan ham ko‘rsatiladi, faqat rangga bog‘liq emas.
- Kichik ekranlarda oyna ichini aylantirish mumkin; klaviatura fokusiga aniq chegara berilgan.
- Asosiy amal tugmasi va matn ranglari o‘qilishi uchun to‘q fon bilan tanlangan.
