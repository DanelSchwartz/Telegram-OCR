# Telegram OCR Scanner

סורק תמונות בקבוצות/ערוצי טלגרם, מריץ OCR (Tesseract), ומייצא הודעות שבהן הטקסט בתמונה מכיל מילות מפתח
(התאמה עמידה לשגיאות OCR, כולל עברית).

## התקנה
```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
התקן Tesseract + חבילות שפה:
- Windows: https://github.com/UB-Mannheim/tesseract/wiki (בחר Hebrew/Arabic/Russian בהתקנה)
- Linux: `sudo apt install tesseract-ocr tesseract-ocr-heb tesseract-ocr-ara tesseract-ocr-rus`
- macOS: `brew install tesseract tesseract-lang`

הגדרות: העתק `.env.example` ל-`.env` ומלא `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` (מ-https://my.telegram.org).
בהרצה הראשונה Telethon ישאל קוד אימות. קובץ ה-session נשמר ב-`data/` (לעולם לא לעלות ל-GitHub).

## שימוש
```bash
# היסטוריה: עד 500 תמונות אחרונות מהקבוצה
python main.py history -c @somegroup -k "invoice,סיסמה" --limit 500

# זמן אמת, כמה קבוצות
python main.py realtime -c @group1 -c -1001234567890 -k "leak,dump"

# כל הקבוצות/ערוצים, מילות מפתח מקובץ, פלט CSV
python main.py history --keywords-file words.txt --format csv --limit 0

# מצב אינטראקטיבי (כמו בגרסה המקורית)
python main.py
```
אפשרויות עיקריות: `--threshold 85` (רגישות התאמה), `--langs eng+heb` (פחות שפות = מהיר ומדויק יותר),
`--concurrency 2`, `--no-save-images`, `--include-private`, `--tesseract-cmd`.

פלט: `data/exports/export.jsonl` (או `.csv`), תמונות תואמות ב-`data/matched_images/`, לוג ב-`data/logs/`.
הרצה חוזרת לא מייצאת שוב הודעות שכבר יוצאו.

## מה תוקן לעומת הגרסה המקורית
- `process_image_for_ocr` החזיר רשימה אבל הקוד טיפל בו כנתיב בודד. עכשיו הווריאנטים נוצרים בזיכרון (בלי קבצי `_filterN`).
- `iter_messages` הוא async iterator, והלולאה שימשה `for` רגיל. תוקן ל-`async for`, כולל סינון ישיר לתמונות.
- מצב Real-Time מומש באמת (`events.NewMessage`). קודם הוא סרק את כל ההיסטוריה.
- `found_match`/`file_path` לא מוגדרים בנתיבי כשל, ו-`await` חסר בקריאות async. תוקן.
- בדיקת Tesseract רצה ב-import וביקשה `input()`. עכשיו: PATH, `TESSERACT_CMD`, נתיבי Windows, ואימות חבילות שפה.
- `ZeroDivisionError` במילת מפתח ריקה. נוספו ניקוי מילים, התאמה עם `rapidfuzz`, נרמול עברית (ניקוד, פיסוק) ושימוש בהתאמת מילה שלמה למילים קצרות.
- OCR נעצר בווריאנט הראשון שמתאים (הרבה יותר מהיר) ורץ ב-`asyncio.to_thread` עם הגבלת מקביליות.
- יצוא JSONL/CSV במקום שכתוב קובץ JSON שלם בכל הודעה, עם מניעת כפילויות מתמשכת.
- קישורים להודעות נבנים נכון (שם משתמש ציבורי או `t.me/c/<id>`).
- חבילות חסרות/מתנגשות ב-requirements (`pytesseract`, `rapidfuzz`; הוסרה התנגשות opencv). OpenCV אופציונלי.

## בדיקות
```bash
pip install -r requirements-dev.txt && python -m pytest
```
