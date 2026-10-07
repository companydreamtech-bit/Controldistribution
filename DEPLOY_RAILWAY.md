# 🚀 Railway.app platformasiga botni deploy qilish bo'yicha qo'llanma

"CONTROL PRIBOR" Telegram botini Railway platformasiga 24/7 rejimda to'xtovsiz ishlashi uchun to'liq tayyorladik. Loyiha Dockerfile, Nixpacks va Procfile konfiguratsiyalari bilan ta'minlangan.

---

## ⚠️ MUHIM QOIDA (Telegram 409 Conflict xatoligini oldini olish)
Bitta Telegram bot tokeni bilan bir vaqtda **faqat 1 ta** joyda long-polling ishlashi mumkin. 
Railway'da botni yoqishdan oldin **kompyuteringizda (lokalda) ishlab turgan botni to'xtatishingiz shart**. Aks holda Telegram ikkala tomondan ham yangilanishlarni qabul qilishga urinib, `Conflict: terminated by other getUpdates request` xatosini beradi.

---

## 🛠 1-USUL: GitHub orqali Deploy qilish (Tavsiya etiladi - Eng oson)

### 1-qadam: Loyihani GitHub'ga yuklash
Agar loyihangiz hali GitHub'da bo'lmasa, quyidagi buyruqlar orqali yangi repozitoriy yarating:
```bash
git init
git add .
git commit -m "feat: prepare bot for Railway deployment"
git branch -M main
git remote add origin https://github.com/USERNAME/REPO_NAME.git
git push -u origin main
```
*(Eslatma: `.gitignore` sozlangani sababli maxfiy `.env` fayli va keshlar GitHub'ga chiqib ketmaydi).*

---

### 2-qadam: Railway'da yangi loyiha yaratish
1. [Railway.app](https://railway.app) saytiga kiring va ro'yxatdan o'ting / kiring.
2. Bosh sahifada **"New Project"** tugmasini bosing.
3. **"Deploy from GitHub repo"** ni tanlang va o'zingizning bot repozitoriyangizni tanlang.

---

### 3-qadam: Muhit o'zgaruvchilarini (Variables) kiritish
Deploy boshlanishi bilanoq yoki loyiha sozlamalarida:
1. Loyiha ichidagi servisga bosing va yuqori menyudan **"Variables"** bo'limiga o'ting.
2. **"New Variable"** tugmasini bosib, quyidagi o'zgaruvchilarni kiriting:

| O'zgaruvchi nomi (Key) | Qiymati (Value) | Izoh |
| :--- | :--- | :--- |
| `BOT_TOKEN` | `8866907161:AAFojv4-y5FKoO_NnaXlaQsOj9o8Yr67FVM` | BotFather'dan olingan token |
| `ORDER_GROUP_ID` | `-1004469883088` | Buyurtmalar tushadigan guruh IDsi |
| `BASE_URL` | `https://controlpribor.uz` | Sayt manzili |
| `PYTHONUNBUFFERED` | `1` | Loglarni darhol konsolda ko'rsatish |

3. O'zgaruvchilarni saqlaganingizdan so'ng, Railway avtomatik ravishda qayta ishga tushadi (Redeploy).

---

### 4-qadam (Ixtiyoriy, lekin tavsiya qilinadi): Doimiy xotira (Volume) ulash
Railway har safar qayta deploy bo'lganda fayl tizimini yangilaydi. Barcha 100 ta tovar va kategoriyalar Docker fayli ichiga o'rnatilgan bo'lib, darhol ishlaydi. 
Biroq, yangi ro'yxatdan o'tgan foydalanuvchilar va buyurtmalar tarixi qayta deploy bo'lganda ham o'chib ketmasligi uchun Railway Volume qo'shish tavsiya etiladi:

1. Railway loyiha oynasida bo'sh joyga sichqonchaning o'ng tugmasini bosing yoki `Ctrl+K` -> **Volume** qo'shing.
2. Volume sozlamalarida **Mount Path** ga quyidagini yozing:
   ```text
   /app/data
   ```
3. Servisning **Variables** bo'limiga yana bitta o'zgaruvchi qo'shing:
   ```text
   DB_PATH=/app/data/database.db
   ```
4. *Botimiz kodi aqlli qilib yozilgan:* agar `/app/data/database.db` fayli hali bo'lmasa, u avtomatik ravishda tayyorlangan 100 ta tovarli bazani ushbu volume'ga nusxalab oladi va saqlaydi!

---

## 💻 2-USUL: Railway CLI orqali to'g'ridan-to'g'ri terminaldan Deploy qilish

Agar GitHub'siz to'g'ridan-to'g'ri o'z kompyuteringizdan yuklamoqchi bo'lsangiz:

1. Railway CLI ni o'rnating (agar o'rnatilmagan bo'lsa):
   ```bash
   npm i -g @railway/cli
   ```
2. Tizimga kiring:
   ```bash
   railway login
   ```
3. Loyiha papkasida:
   ```bash
   railway init
   ```
4. O'zgaruvchilarni o'rnating:
   ```bash
   railway variables set BOT_TOKEN="8866907161:AAFojv4-y5FKoO_NnaXlaQsOj9o8Yr67FVM" ORDER_GROUP_ID="-1004469883088" BASE_URL="https://controlpribor.uz"
   ```
5. Deploy qiling:
   ```bash
   railway up
   ```

---

## 🔍 Loglarni kuzatish va tekshirish
Deploy tugagach, Railway boshqaruv panelidagi **"Deployments"** -> **"View Logs"** tugmasini bosing.
U yerda quyidagi yozuv paydo bo'lishi kerak:
```text
[INFO] - Ma'lumotlar bazasi tayyorlandi.
[INFO] - Bot muvaffaqiyatli ishga tushdi va xabarlarni qabul qilmoqda!
```
Shundan so'ng Telegram'da botingizga `/start` yuborib tekshirib ko'rishingiz mumkin!
