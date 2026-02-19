import os
import re
import time
import requests
import threading
from collections import Counter
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from deep_translator import GoogleTranslator

# IMAGE SAVE DIRECTORY
IMAGE_SAVE_DIR = "article_images"
os.makedirs(IMAGE_SAVE_DIR, exist_ok=True)

def get_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    return driver

# ACCEPT COOKIE BANNER
def accept_cookies(driver):
    try:
        btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable(
                (By.XPATH,
                 "//button[contains(text(),'Aceptar') or "
                 "contains(text(),'ACEPTAR') or "
                 "contains(@id,'accept') or "
                 "contains(@class,'accept')]")
            )
        )
        btn.click()
        time.sleep(1)
    except Exception:
        pass

# DOWNLOAD IMAGE
def download_image(url: str, filename: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            filepath = os.path.join(IMAGE_SAVE_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(response.content)
            print(f"Image saved → {filepath}")
        else:
            print(f"Could not download image (HTTP {response.status_code})")
    except Exception as e:
        print(f"Image download error: {e}")

def get_image_from_article_page(driver, url: str) -> str:
    img_url = None
    main_window = driver.current_window_handle
    try:
        driver.execute_script("window.open(arguments[0]);", url)
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(2)
        image_selectors = [
            "figure.a_e_m img",      
            "figure img[src]",
            ".a_m img", 
            "picture img",
            "article img",               
        ]
        for selector in image_selectors:
            try:
                img_el = driver.find_element(By.CSS_SELECTOR, selector)
                candidate = (
                    img_el.get_attribute("src") or
                    img_el.get_attribute("data-src") or
                    img_el.get_attribute("data-lazy-src")
                )
                if candidate and candidate.startswith("http") and not candidate.endswith(".svg"):
                    img_url = candidate
                    break
            except Exception:
                continue

    except Exception as e:
        print(f"    Image page error: {e}")
    finally:
        try:
            driver.close()
            driver.switch_to.window(main_window)
        except Exception:
            pass

    return img_url

def get_article_content(driver, url: str) -> str:
    content = ""
    main_window = driver.current_window_handle
    try:
        driver.execute_script("window.open(arguments[0]);", url)
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(2)
        accept_cookies(driver)
        content_selectors = [
            "div.a_c p",
            "div[data-dtm-region='articulo_cuerpo'] p",
            "div.article_body p",
            "section.articulo-cuerpo p",
        ]

        for selector in content_selectors:
            try:
                paras = driver.find_elements(By.CSS_SELECTOR, selector)
                text_parts = [
                    p.text.strip() for p in paras
                    if p.text.strip() and len(p.text.strip()) > 40
                ]
                if text_parts:
                    content = " ".join(text_parts[:6])
                    break
            except Exception:
                continue
        if not content:
            try:
                paras = driver.find_elements(
                    By.XPATH,
                    "//article//p[not(ancestor::aside) and "
                    "not(ancestor::nav) and "
                    "not(ancestor::*[@class and contains(@class,'related')]) and "
                    "not(ancestor::*[@class and contains(@class,'sidebar')])]"
                )
                text_parts = [
                    p.text.strip() for p in paras
                    if p.text.strip() and len(p.text.strip()) > 40
                ]
                content = " ".join(text_parts[:6])
            except Exception:
                pass

    except Exception as e:
        print(f"Content page error: {e}")
    finally:
        try:
            driver.close()
            driver.switch_to.window(main_window)
        except Exception:
            pass

    return content

def scrape_opinion_articles(driver):
    print("Verifying El País is in Spanish")

    driver.get("https://elpais.com")
    time.sleep(3)
    accept_cookies(driver)

    lang = driver.find_element(By.TAG_NAME, "html").get_attribute("lang")
    print(f"Page language attribute: '{lang}'")
    if lang and "es" in lang.lower():
        print("Confirmed: Website is in Spanish.")
    else:
        print("Language attribute unexpected — proceeding anyway.")
    print("Scraping Opinion Section Articles")

    driver.get("https://elpais.com/opinion/")
    time.sleep(4)
    accept_cookies(driver)
    print(f"Current URL: {driver.current_url}")
    articles_raw = []
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article h2, article h3"))
        )

        article_elements = driver.find_elements(By.CSS_SELECTOR, "article")
        for art in article_elements:
            try:
                try:
                    title_el = art.find_element(By.CSS_SELECTOR, "h2, h3")
                    title = title_el.text.strip()
                except Exception:
                    continue

                if not title:
                    continue
                try:
                    link_el = title_el.find_element(By.TAG_NAME, "a")
                    link = link_el.get_attribute("href")
                except Exception:
                    try:
                        link_el = art.find_element(By.CSS_SELECTOR, "a")
                        link = link_el.get_attribute("href")
                    except Exception:
                        link = None
                img_url = None
                try:
                    img_el = art.find_element(By.CSS_SELECTOR, "img")
                    img_url = (
                        img_el.get_attribute("src") or
                        img_el.get_attribute("data-src") or
                        img_el.get_attribute("data-lazy-src")
                    )
                    if img_url and (img_url.endswith(".svg") or "icon" in img_url.lower()):
                        img_url = None
                except Exception:
                    pass

                articles_raw.append({
                    "title":   title,
                    "link":    link,
                    "img_url": img_url,
                })

                if len(articles_raw) >= 5:
                    break

            except Exception:
                continue

    except Exception as e:
        print(f"Article listing error: {e}")

    print(f"Found {len(articles_raw)} articles on listing page.")
    articles_data = []

    for idx, raw in enumerate(articles_raw, start=1):
        print(f"\n  Fetching article {idx}: {raw['title']}")

        img_url = raw["img_url"]
        content = ""

        if raw["link"]:
            main_window = driver.current_window_handle
            try:
                driver.execute_script("window.open(arguments[0]);", raw["link"])
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(2)
                accept_cookies(driver)
                content_selectors = [
                    "div.a_c p",
                    "div[data-dtm-region='articulo_cuerpo'] p",
                    "div.article_body p",
                ]
                for selector in content_selectors:
                    try:
                        paras = driver.find_elements(By.CSS_SELECTOR, selector)
                        text_parts = [
                            p.text.strip() for p in paras
                            if p.text.strip() and len(p.text.strip()) > 40
                        ]
                        if text_parts:
                            content = " ".join(text_parts[:6])
                            break
                    except Exception:
                        continue
                if not content:
                    try:
                        paras = driver.find_elements(
                            By.XPATH,
                            "//article//p[not(ancestor::aside) and "
                            "not(ancestor::nav) and "
                            "not(ancestor::*[contains(@class,'related')]) and "
                            "not(ancestor::*[contains(@class,'sidebar')])]"
                        )
                        text_parts = [
                            p.text.strip() for p in paras
                            if p.text.strip() and len(p.text.strip()) > 40
                        ]
                        content = " ".join(text_parts[:6])
                    except Exception:
                        pass
                if not img_url:
                    image_selectors = [
                        "figure.a_e_m img",
                        "figure img[src]",
                        ".a_m img",
                        "picture source",
                        "picture img",
                    ]
                    for selector in image_selectors:
                        try:
                            img_el = driver.find_element(By.CSS_SELECTOR, selector)
                            candidate = (
                                img_el.get_attribute("src") or
                                img_el.get_attribute("srcset") or
                                img_el.get_attribute("data-src")
                            )
                            if candidate and "http" in candidate and not candidate.endswith(".svg"):
                                img_url = candidate.split(",")[0].split(" ")[0].strip()
                                break
                        except Exception:
                            continue

                driver.close()
                driver.switch_to.window(main_window)

            except Exception as e:
                print(f"    Article page error: {e}")
                try:
                    driver.switch_to.window(main_window)
                except Exception:
                    pass

        articles_data.append({
            "index":   idx,
            "title":   raw["title"],
            "content": content or "(Content not available — article may be paywalled)",
            "img_url": img_url,
            "link":    raw["link"],
        })

    print(f"\n\nSuccessfully processed {len(articles_data)} articles.\n")

    for art in articles_data:
        print(f"\nArticle {art['index']}: {art['title']}")
        print(f"Content (Spanish):")
        print(f"{art['content'][:500]}{'...' if len(art['content']) > 500 else ''}")

        if art["img_url"]:
            img_filename = f"article_{art['index']}_cover.jpg"
            download_image(art["img_url"], img_filename)
        else:
            print("No cover image found for this article.")

    return articles_data
def translate_headers(articles_data):
    print("Translating Titles to English")

    translator = GoogleTranslator(source="es", target="en")
    translated = []

    for art in articles_data:
        try:
            english_title = translator.translate(art["title"])
        except Exception as e:
            print(f"  Translation error for article {art['index']}: {e}")
            english_title = art["title"]

        translated.append(english_title)
        print(f"\n  [{art['index']}] ES: {art['title']}")
        print(f"EN: {english_title}")

    return translated
def analyze_repeated_words(translated_titles):
    print("Repeated Word Analysis")

    STOP_WORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "it", "its", "this",
        "that", "are", "was", "be", "as", "he", "she", "we", "they",
        "i", "you", "his", "her", "my", "our", "their", "have", "has",
        "had", "not", "no", "so", "if", "do", "did", "will", "can",
        "more", "up", "out", "what", "who", "how", "all", "about",
        "into", "than", "after", "over", "your",
    }

    all_words = []
    for title in translated_titles:
        words    = re.findall(r"[a-zA-Z]+", title.lower())
        filtered = [w for w in words if w not in STOP_WORDS and len(w) > 2]
        all_words.extend(filtered)

    word_counts = Counter(all_words)
    repeated    = {word: count for word, count in word_counts.items() if count > 2}

    if repeated:
        print("\nWords repeated more than twice across all titles:\n")
        for word, count in sorted(repeated.items(), key=lambda x: -x[1]):
            print(f"    '{word}' → {count} occurrences")
    else:
        print("\n  No words repeated more than twice.")
        print("\n  Word frequency reference (top 10):")
        for word, count in word_counts.most_common(10):
            print(f"    '{word}' → {count}")

    return repeated
def main():
    print("\nStarting El País Opinion Section Scraper")
    driver = get_driver()

    try:
        articles_data = scrape_opinion_articles(driver)
        if not articles_data:
            print("\nNo articles found. Exiting.")
            return
        translated_titles = translate_headers(articles_data)

        analyze_repeated_words(translated_titles)

    except Exception as e:
        print(f"\nFatal error: {e}")
        raise

    finally:
        driver.quit()
        print("\nBrowser session closed.")

if __name__ == "__main__":
    main()