from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By  # Import By
from InquirerPy import inquirer
from bs4 import BeautifulSoup
from video_downloader import record_stream
import time
import json
import webbrowser

BASE_URL = "https://playsight.com"
WEB_URL = "https://web.playsight.com"
url = WEB_URL + "/facility/danube-sports-world-paddle/home"


def fetch_page(url):
    # Set up Chrome options and enable network interception
    options = Options()
    options.headless = True  # Run in headless mode
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-sandbox")

    # Enable network logging
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    # Initialize the driver with the updated options
    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=options
    )

    driver.get(url)
    time.sleep(6)  # Wait for the page to fully load (adjust as needed)

    html = driver.page_source
    logs = driver.get_log("performance")  # Capture network logs
    return driver, html, logs  # Return the driver for reuse


def parse_video_items(html):
    soup = BeautifulSoup(html, "html.parser")

    videos = []
    broadcasting_courts = soup.find_all("ps-broadcasting-court")

    for court in broadcasting_courts:
        actions_div = court.find("div", class_="actions")
        name_div = court.find("div", class_="name")
        if actions_div and name_div:
            link_tag = actions_div.find("a", href=True)
            name_tag = name_div.find("span")
            if link_tag and name_tag:
                href = link_tag["href"]
                name = name_tag.get_text(strip=True)
                videos.append((name, href))
            else:
                print("No link found in actions.")
        else:
            print("No actions div found.")

    return videos


# Toggles user to select stream to record
def select_match(videos):
    # Create a menu to select a match by its name
    selected_match_name = inquirer.select(
        message="Select a match to download the page:",
        choices=[match_name for match_name, _ in videos],
    ).execute()

    # Find the URL corresponding to the selected match name
    selected_match = next(
        (video for video in videos if video[0] == selected_match_name), None
    )
    return selected_match  # Return the full (name, href) tuple


def save_logs_to_file(logs, file_path="network_logs.txt"):
    with open(file_path, "w") as file:
        for entry in logs:
            file.write(entry["message"] + "\n")
    print(f"Logs saved to {file_path}")


def sign_in(driver):
    # Navigate to the login page
    driver.get(WEB_URL + "/auth")
    time.sleep(3)

    # Ask the user for email and password
    print("In order to record a stream please sign into PlaySight \n")
    email = input("Enter your email: ")
    password = input("Enter your password: ")

    # Find the input fields for the username and password
    email_field = driver.find_element(
        By.XPATH, '//input[@type="email" and @autocomplete="email"]'
    )
    password_field = driver.find_element(
        By.XPATH, '//input[@type="password" and @autocomplete="password"]'
    )

    # Enter the user's credentials
    email_field.send_keys(email)
    password_field.send_keys(password)

    # Submit the form (find the login button and click it)
    login_button = driver.find_element(
        By.XPATH, '//button[@type="submit"]'
    )  # Adjust the XPath as needed
    login_button.click()
    time.sleep(5)  # Wait for the login process to complete


# Extract stream link
def link_from_logs(logs):
    # Iterate through the logs to find the first .m3u8 URL
    for entry in logs:
        try:
            # Attempt to parse the log entry's message (which may not always be valid JSON)
            log_message = json.loads(entry["message"])

            # Ensure the log message contains network information and is the right method (responseReceived)
            if (
                "message" in log_message
                and "method" in log_message["message"]
                and log_message["message"]["method"] == "Network.responseReceived"
            ):
                response = log_message["message"]["params"]["response"]

                # Check if the response URL contains '.m3u8'
                url = response.get("url", "")
                if ".m3u8" in url:
                    return url  # Return the first .m3u8 URL found and stop the loop
        except json.JSONDecodeError:
            print("Error decoding JSON for entry:", entry)
        except KeyError as e:
            print(f"Error with log entry keys: {e} - Skipping entry.")
        except Exception as e:
            print(f"Unexpected error: {e} - Skipping entry.")

    return None  # Return None if no .m3u8 URL is found


if __name__ == "__main__":
    driver, html, logs = fetch_page(url)  # Initial page load
    sign_in(driver)
    videos = parse_video_items(html)
    if not videos:
        print("No live streams available")
    else:
        # User select match to record
        selected_match = select_match(videos)
        match_name, match_url = selected_match
        print(f"Selected Match: {match_name}, URL: {match_url}")

        # Navigate to stream
        driver.get(
            "https://web.playsight.com" + match_url
        )  # Make sure you use the full URL if 'match_url' is just a relative path
        time.sleep(10)
        # Capture performance logs to extract .m3u8
        performance_logs = driver.get_log("performance")
        link = link_from_logs(performance_logs)
        output_file = "out/livestream_recording.mp4"
        record_stream(link, output_file)

        driver.quit()  # Close the driver after operation