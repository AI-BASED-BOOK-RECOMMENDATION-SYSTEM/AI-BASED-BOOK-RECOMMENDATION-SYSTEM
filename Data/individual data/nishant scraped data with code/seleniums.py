

import time
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException


CHROMEDRIVER_PATH = r"C:\projects\chromedriver-win64\chromedriver.exe"  
GENRE_URL = "https://www.goodreads.com/list/show/1112.Best_Thrillers"
MAX_BOOKS = 4000
DELAY = 1 
CSV_FILE = "mysterythriller_4000.csv"


options = Options()
options.add_argument("--start-maximized")

service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 10)


csv_file = open(CSV_FILE, "w", newline='', encoding='utf-8')
csv_writer = csv.writer(csv_file)
csv_writer.writerow(["Title", "Author", "Genres", "Avg_Rating", "Num_Ratings", "Num_Reviews", "Description", "Book_URL"])

total_saved = 0
page = 1

while total_saved < MAX_BOOKS:
    driver.get(f"{GENRE_URL}?page={page}")
    time.sleep(2)

    try:
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.bookTitle")))
        book_anchors = driver.find_elements(By.CSS_SELECTOR, "a.bookTitle")
    except TimeoutException:
        print(f"No books found on page {page}")
        break

    for index in range(len(book_anchors)):
        if total_saved >= MAX_BOOKS:
            break
        try:
           
            anchor = driver.find_elements(By.CSS_SELECTOR, "a.bookTitle")[index]
            book_url = anchor.get_attribute("href")
            if not book_url:
                continue

            driver.get(book_url)
            time.sleep(DELAY)

            try:
                title = driver.find_element(By.CSS_SELECTOR, "h1[data-testid='bookTitle']").text.strip()
            except NoSuchElementException:
                title = "N/A"

            try:
                authors = driver.find_elements(By.CSS_SELECTOR, "span[data-testid='name']")
                author = ", ".join([a.text.strip() for a in authors]) if authors else "N/A"
            except:
                author = "N/A"

            try:
                genre_container = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='genresList']"))
                )
                genre_elements = genre_container.find_elements(By.CSS_SELECTOR, "span.BookPageMetadataSection__genreButton a span.Button__labelItem")
                genres = ", ".join([g.text.strip() for g in genre_elements if g.text.strip() != ""]) if genre_elements else "N/A"
            except:
                genres = "N/A"

            try:
                description = driver.find_element(By.CSS_SELECTOR, "div.DetailsLayoutRightParagraph span.Formatted").text.strip()
            except:
                description = "N/A"

            try:
                avg_rating = driver.find_element(By.CSS_SELECTOR, "div.RatingStatistics__rating").text.strip()
            except:
                avg_rating = "N/A"

            try:
                num_ratings = driver.find_element(By.CSS_SELECTOR, "span[data-testid='ratingsCount']").text.strip()
            except:
                num_ratings = "N/A"

            try:
                num_reviews = driver.find_element(By.CSS_SELECTOR, "span[data-testid='reviewsCount']").text.strip()
            except:
                num_reviews = "N/A"

         
            csv_writer.writerow([title, author, genres, avg_rating, num_ratings, num_reviews, description, book_url])
            csv_file.flush()
            total_saved += 1
            print(f"[{total_saved}] Scraped: {title}")

            driver.back()
            time.sleep(DELAY)

        except (StaleElementReferenceException, TimeoutException) as e:
            print("Skipped a book due to error:", e)
            driver.get(f"{GENRE_URL}?page={page}")
            time.sleep(DELAY)
            continue

    print(f" Finished page {page}")
    page += 1

driver.quit()
csv_file.close()
print(f"\n Scraping finished. Total books scraped: {total_saved}")
