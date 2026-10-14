import subprocess
import sys
import time
import threading

# این فایل هر دو بات رو همزمان، داخل همین یه سرویس/کانتینر، اجرا
# می‌کنه، تا هر دو روی همون فایل‌سیستم (و در نتیجه همون users.json)
# کار کنن. اگه یکیشون به هر دلیلی کرش کرد، بعد از ۵ ثانیه خودکار
# دوباره روشن می‌شه (بدون این‌که اون یکی بات متوقف بشه).

SCRIPTS = ["main_test.py", "harley.py"]


def run_forever(script):
    while True:
        print(f"🚀 در حال اجرای {script} ...")
        proc = subprocess.run([sys.executable, script])
        print(f"⚠️ {script} با کد {proc.returncode} متوقف شد. ۵ ثانیه دیگه دوباره اجرا می‌شه...")
        time.sleep(5)


if __name__ == "__main__":
    threads = [threading.Thread(target=run_forever, args=(s,), daemon=True) for s in SCRIPTS]

    for t in threads:
        t.start()

    for t in threads:
        t.join()
