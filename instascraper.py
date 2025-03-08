import pyodbc
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time

class InstagramScraper:
    def __init__(self, username, password, server, database):
        self.username = username
        self.password = password
        self.ids = []
        self.driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()))
        self.conn = self.connect_to_db(server, database)
        self.cursor = self.conn.cursor()

    def connect_to_db(self, server, database):
        connection_string = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'
        return pyodbc.connect(connection_string)

    def setup_db(self):
        # حذف داده‌های قدیمی و ایجاد جدول در صورت نبود آن
        self.cursor.execute('''DELETE FROM InstagramComments''')
        self.cursor.execute('''
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'InstagramComments')
        CREATE TABLE InstagramComments (
            PostURL NVARCHAR(500),
            Username NVARCHAR(100),
            Comment NVARCHAR(MAX),
            CommentDate DATETIME DEFAULT GETDATE()
        )''')
        self.conn.commit()

    def login(self):
        try:
            self.driver.get("https://www.instagram.com/")
            
            # وارد کردن نام کاربری و رمز عبور
            username_input = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='username']"))
            )
            password_input = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password']"))
            )

            username_input.send_keys(self.username)
            password_input.send_keys(self.password)
            
            # کلیک روی دکمه ورود
            submit = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            submit.click()

            # منتظر برای حل کردن CAPTCHA
            print("Please solve the CAPTCHA and press Enter...")
            input("Press Enter after solving the CAPTCHA")

            # چک کردن احراز هویت دو مرحله‌ای
            try:
                code = input("Enter the verification code: ")
                verification = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='verificationCode']"))
                )
                verification.send_keys(code)
                submit_verification = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='button']"))
                )
                submit_verification.click()
            except:
                print("Two-factor authentication not required.")
        except Exception as e:
            print(f"An error occurred during login: {e}")

    def skip_popups(self):
        try:
            time.sleep(20)
            not_now_button = WebDriverWait(self.driver, 60).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(),'اکنون نه')]"))
            )
            not_now_button.click()
        except Exception as e:
            print("No pop-ups to skip:", e)

    def add_user_ids(self):
        while True:
            user_id = input("Enter Id You Want to Scrape (or press Enter to finish): ")
            if not user_id:
                break
            self.ids.append(user_id)

    def scrape_posts(self, user_id):
        self.driver.get(f"https://www.instagram.com/{user_id}/")
        time.sleep(20)

        posts = []
        links = self.driver.find_elements(By.TAG_NAME, 'a')
        for link in links:
            post = link.get_attribute('href')
            if post and ('/p/' in post or '/reel/' in post):
                posts.append(post)

        return list(dict.fromkeys(posts))[:10]

    def scrape_comments(self, post_url):
        self.driver.get(post_url)
        time.sleep(10)
        
        comments_data = []
        try:
            comment_elements = self.driver.find_elements(By.CSS_SELECTOR, 'div._a9zs > span')
            user_elements = self.driver.find_elements(By.CSS_SELECTOR, "h3[class='_a9zc']")

            for comment, user in zip(comment_elements, user_elements):
                username_text = user.text
                comment_text = comment.text
                comments_data.append((post_url, username_text, comment_text))
                
                # ذخیره در پایگاه داده
                self.cursor.execute('''
                    INSERT INTO InstagramComments (PostURL, Username, Comment)
                    VALUES (?, ?, ?)
                ''', post_url, username_text, comment_text)
                self.conn.commit()
        except Exception as e:
            print(f"Error extracting comments from post {post_url}: {e}")
        return comments_data

    def scrape(self):
        self.setup_db()
        self.login()
        self.skip_popups()
        self.add_user_ids()

        all_comments = []

        for user_id in self.ids:
            posts = self.scrape_posts(user_id)
            if posts:
                for post_url in posts:
                    comments = self.scrape_comments(post_url)
                    all_comments.extend(comments)
            else:
                print(f"No posts found for {user_id}")

        self.save_comments_to_file(all_comments)
        print("Scraping completed.")

    def save_comments_to_file(self, comments):
        with open("comments.txt", "w", encoding="utf-8") as file:
            for post_url, username, comment in comments:
                file.write(f"{username}: {comment} (Post: {post_url})\n")
        print("Comments saved to comments.txt")

    def close(self):
        self.driver.quit()
        self.conn.close()


if __name__ == "__main__":
    name = input("Enter Your Instagram Username: ")
    pas = input("Enter Your Instagram Password: ")
    
    server = 'WS131\\CREDITCARD'  # آدرس سرور شما
    database = 'InstagramDB'  # نام دیتابیس شما

    scraper = InstagramScraper(name, pas, server, database)
    scraper.scrape()
    scraper.close()
