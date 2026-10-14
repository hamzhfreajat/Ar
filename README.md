# خادم تطبيق كتابكم

خادم تطبيق الواقع المعزز (Unity). التطبيق لا يحمل مفتاح Azure أبدًا: يرسل تسجيل الطفل إلى هذا الخادم، والخادم يسأل Azure ويعيد درجة واحدة. التسجيلات لا تُحفظ.

| المسار | العمل |
|---|---|
| `GET /v1/health` | هل الخادم يعمل، وهل تقييم النطق مفعّل |
| `POST /v1/devices` | أول تشغيل للتطبيق: يأخذ رمزًا يحتفظ به ويرسله مع كل طلب. لا تسجيل دخول، فالدروس المجانية تعمل كضيف |
| `POST /v1/pronunciation?text=hello` | جسم الطلب ملف WAV (16 kHz، 16 بت، قناة واحدة)، والرد درجة من 100. حد يومي لكل جهاز |
| `PUT /v1/progress/{scene}` | يحفظ إكمال مشهد ونجومه، ويبقي الأفضل دائمًا |
| `GET /v1/progress` | تقدّم الجهاز في كل المشاهد |

الوثائق التفاعلية: `http://localhost:8090/docs` أثناء التشغيل.

## التشغيل محليًا

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt -r requirements-dev.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8090
```

```bash
.venv/Scripts/python -m pytest -q
```

## Docker و Coolify

```bash
docker compose up -d --build
```

- الواجهة على المنفذ **8090**، وقاعدة PostgreSQL غير منشورة على أي منفذ (تصل إليها الواجهة داخل شبكة Docker فقط)، فلا تتعارض مع منافذ sooqcom (5432، 6432، 8080، 3001).
- في Coolify: مشروع جديد من هذا المستودع بنوع **Docker Compose**، وتوضع هذه في **Environment Variables**: `POSTGRES_PASSWORD` و`AZURE_SPEECH_KEY` و`AZURE_SPEECH_REGION`. لا يدخل أي سر إلى المستودع.
- محليًا بلا Docker تبقى طريقة uvicorn أعلاه (SQLite).

## الإعدادات

- مفتاح Azure ومنطقته في `~/.kitabcom/azure-speech.env` (خارج أي مستودع): `AZURE_SPEECH_KEY` و`AZURE_SPEECH_REGION`.
- البقية في `.env` داخل هذا المجلد (مستثنى من git)، وكلها اختيارية:
  - `DATABASE_URL`: الافتراضي ملف SQLite هنا. مع Docker Compose يُضبط تلقائيًا على PostgreSQL
  - `DAILY_PRONUNCIATION_CHECKS`: الافتراضي 60 لكل جهاز في اليوم
  - `MAX_AUDIO_SECONDS`: الافتراضي 10

## تقييم النطق

الدرجة هي دقة النطق (AccuracyScore) من Azure، لا الدرجة العامة (PronScore) لأنها متساهلة: كلمة "yellow" بدل "hello" أخذت 86.8. إذا نُطق صوت واحد في الكلمة بأقل من 30، لا تتجاوز الدرجة 50. بهذا: "hello" = 100، و"yellow" بدل "hello" = 50 (اختُبر مع Azure في 14 أكتوبر 2026 بصوت حاسوب، وأصوات الأطفال ستأخذ أقل، فيُضبط حد النجاح في التطبيق بعد تجربتهم).

## التالي

1. الوصول من الهاتف: Cloudflare Tunnel يعطي الخادم المحلي عنوان HTTPS.
2. حسابات الأهل وملفات الأطفال.
3. الاشتراكات (Google Play وApp Store، أو RevenueCat) ورموز المدارس.
4. قائمة المحتوى: الصفحات والمشاهد وروابط ملفاتها.
5. Alembic بدل `create_all` قبل أول بيانات حقيقية.
