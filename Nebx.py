import os
from selenium import webdriver as uc
from time import sleep
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait as wait
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException, NoSuchWindowException
from selenium.webdriver.common.keys import Keys
from selenium_authenticated_proxy import SeleniumAuthenticatedProxy
from fake_useragent import UserAgent
import random
import urllib.parse
import threading
import atexit
import psutil

file_lock = threading.Lock()
window_width = 1200
window_height = 1000
webs = []
max_concurrent_tasks_cfg = 24
scale_factor = 0.2
chrome_location_sub = r"chrome\App\Chrome-bin\chrome.exe"
script_dir = os.path.dirname(os.path.abspath(__file__))
chrome_location = os.path.join(script_dir, chrome_location_sub)
items_per_row = 4

def load_lines(file_path):
    with open(file_path, "r") as file:
        lines = file.readlines()
    lines = [line.strip() for line in lines]
    return lines

def write_lines(file_path, lines):
    with open(file_path, "w") as file:
        for line in lines:
            file.write(line + "\n")
def remove_line_immediately(line_to_remove, file_path):
    with file_lock:
        with open(file_path, "r", encoding="utf-8") as file, open("temp.txt", "w", encoding="utf-8") as temp:
            for line in file:
                if line.strip() != line_to_remove:
                    temp.write(line)
        os.remove(file_path)
        os.rename("temp.txt", file_path)
        
def remove_line(file_path, line_to_remove):
    with file_lock:
        lines = load_lines(file_path)
        lines.remove(line_to_remove)
        write_lines(file_path, lines)

def handle_error(file_path, line):
    with open(file_path, "a") as file:
        file.write(line + "\n")

def arrange_windows(drivers, items_per_row, window_width, window_height):
    if not drivers:
        print("No drivers to arrange.")
        return
    screen_width = drivers[0].execute_script("return window.screen.availWidth")
    screen_height = drivers[0].execute_script("return window.screen.availHeight")
    for i, driver in enumerate(drivers):
        try:
            x_position = (i % items_per_row) * window_width
            y_position = (i // items_per_row) * window_height
            driver.set_window_position(x_position, y_position)
            driver.set_window_size(window_width, window_height)
        except NoSuchWindowException:
            print(f"Window for driver {i} is no longer available. Skipping arrangement.")

def kill_chrome_drivers():
    """Kill all Chrome processes from a specific location."""
    print("Clean up chrome process")
    isStillExist = 1
    while isStillExist == 1:
        isStillExist = 0  # Assume there are no processes initially
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                if proc.info['name'] == "chrome.exe" and proc.info['exe'] == chrome_location:  # Change to "chrome" if on Unix/Linux
                    proc.kill()
                    print(proc.info['name'])
                    isStillExist = 1  # Found a process, set flag to 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Handle exceptions for processes that no longer exist or can't be accessed
                continue
        if isStillExist == 1:
            sleep(1)        

atexit.register(kill_chrome_drivers)

def task(tokenx, proxy, link_ref, tokens_file, semaphore):
    global webs
    web = None
    try:
        ua = UserAgent()
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        options = ChromeOptions()
        options.add_argument(f"user-agent={user_agent}")
        options.binary_location = chrome_location
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument('--log-level=3')
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-breakpad")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument(f"--force-device-scale-factor={scale_factor}")
        options.add_argument("--no-sandbox")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])  # Exclude "enable-automation" switch
        options.add_argument('--disable-blink-features=AutomationControlled')  # Disable blink features
        chrome_prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", chrome_prefs)
        options.add_argument("--disable-javascript")
        options.add_argument("--page-load-strategy=none")
        options.add_argument("--disable-hardware-acceleration")
        
        username, password_host_port = proxy.split('@')[0], proxy.split('@')[1]
        username, password = username.split(':')
        host, port = password_host_port.split(':')

        proxy_url = f"http://{username}:{password}@{host}:{port}"
        proxy_helper = SeleniumAuthenticatedProxy(proxy_url=proxy_url)
        proxy_helper.enrich_chrome_options(options)
        web = uc.Chrome(options=options)
        webs.append(web)
        arrange_windows(webs, items_per_row, window_width, window_height)
        current = web.current_window_handle
        
        web.get("https://x.com/")
        wait(web, 5).until(EC.presence_of_element_located((By.XPATH, "//*[text()[contains(.,'Home')]]"))) # Ensure the domain is loaded
        web.add_cookie({'name': 'auth_token', 'value': tokenx, 'domain': 'x.com'})
        web.refresh()
        print("Log in X Complete")
        
        try:
            wait(web, 5).until(EC.presence_of_element_located((By.XPATH, "//*[text()[contains(.,'Your account has been locked.')]]"))) 
            print("Account X has been locked.")
            remove_line(tokens_file, tokenx)
            return
        except:
            pass
        web.get(link_ref)
        wait(web, 30).until(EC.presence_of_element_located((By.XPATH, 
        "//*[text()[contains(.,'Check Your X Account')]]"))) 
        
        wait(web, 10).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "/html/body/div[1]/div/div/div/div/div[3]",
            )
        )
        ).click()
        wait(web, 100).until(EC.presence_of_element_located((By.XPATH, 
            "//*[text()[contains(.,'Sign in to X')]]"))) 
        original_url = web.current_url
        parsed_url = urllib.parse.urlparse(original_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)

        inner_url = query_params['redirect_after_login'][0]
        decoded_inner_url = urllib.parse.unquote(inner_url)
        inner_parsed_url = urllib.parse.urlparse(decoded_inner_url)
        inner_query_params = urllib.parse.parse_qs(inner_parsed_url.query)

        new_scheme = "https"
        new_netloc = "x.com"
        new_path = inner_parsed_url.path
        new_query_params = {k: v[0] for k, v in inner_query_params.items()}

        new_url = urllib.parse.urlunparse((
            new_scheme,
            new_netloc,
            new_path,
            inner_parsed_url.params,
            urllib.parse.urlencode(new_query_params, doseq=True),
            inner_parsed_url.fragment
        ))
        web.get(new_url)
        print("Linked X Complete")
        # input("press any key to continue")
        wait(web, 30).until(EC.presence_of_element_located((By.XPATH, 
        "//*[text()[contains(.,'wants to access your X account')]]"))) 
        wait(web, 10).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "/html/body/div[1]/div/div/div[2]/main/div/div/div[2]/div/div/div[1]/div[3]/button",
                    
                )
            )
        ).click()
        # input("press any key to continue")
        # sleep(5)
        
        try:
            wait(web, 10).until(EC.presence_of_element_located((By.XPATH, "//*[text()[contains(.,'Account rating')]]")))
            print("Recheck REF thành công")
            remove_line(tokens_file, tokenx)
            print(f"Remove token: {tokenx}")
            wait(web, 30).until(EC.presence_of_element_located((By.XPATH, 
            "//*[text()[contains(.,'Discover. Create. Thrive.')]]"))) 
            web.close()
            web.quit()
            return
        except:
            pass
        wait(web, 30).until(EC.presence_of_element_located((By.XPATH, 
        "//*[text()[contains(.,'View rewards')]]"))) 
        wait(web, 100).until(EC.presence_of_element_located((By.XPATH, 
        "/html/body/div[1]/div/div/div/div/div[4]"))).click()
        wait(web, 100).until(EC.presence_of_element_located((By.XPATH, 
        "/html/body/div[1]/div/div/div/div/div[5]"))).click()

        # input("press any key to continue")
        print("REF Ok")
        remove_line(tokens_file, tokenx)
        print(f"Remove token: {tokenx}")
        sleep(15)
        wait(web, 30).until(EC.presence_of_element_located((By.XPATH, 
        "//*[text()[contains(.,'Discover. Create. Thrive.')]]"))) 
        web.close()
        web.quit()

    except NoSuchWindowException:
        print("Caught NoSuchWindowException. Skipping operation.")
        handle_error("fail_token.txt", tokenx)

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        handle_error("fail_token.txt", tokenx)
    finally:
        if web:
            try:
                if web in webs:
                    webs.remove(web)
                web.quit()  # This will close all associated windows and end the session
            except Exception as e:
                print(f"Error while quitting WebDriver: {str(e)}")
            finally:
                web = None
                semaphore.release()

def main():
    proxy_file = "proxy.txt"
    linkref_file = "linkref.txt"
    tokens_file = "token.txt"
    
    proxies = load_lines(proxy_file)
    links = load_lines(linkref_file)
    tokens = load_lines(tokens_file)
    max_concurrent_tasks_cfg = int(input("Enter your threads : "))
    semaphore = threading.Semaphore(max_concurrent_tasks_cfg)
    
    threads = []
    retry = 3
    while len(tokens)>0 and retry >0:
        retry -=1
        kill_chrome_drivers()
        for  tokenx in  tokens:
            proxy = random.choice(proxies)
            link_ref = random.choice(links)
            semaphore.acquire()
            t = threading.Thread(target=task, args=(tokenx, proxy, link_ref,tokens_file, semaphore))
            t.start()
            threads.append(t)
            while threading.active_count() > max_concurrent_tasks_cfg:
                timerthread =0
                while threading.active_count()>1:
                    timerthread +=1
                    threadcount = threading.active_count()
                    sleep(1)
                    threadcount_1 = threading.active_count()
                    if threadcount_1 < threadcount:
                        print (f"threading.active_count() {threadcount_1}")
                    if timerthread > 300:
                        print ("Terminate thread after 5 mins waiting")
                        kill_chrome_drivers()
                        timerthread = 0
                kill_chrome_drivers()
                print ("Threads cleaned up already")
        for t in threads:
            t.join()
        tokens = load_lines(tokens_file)
if __name__ == '__main__':
    main()
