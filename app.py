import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
import streamlit.components.v1 as components
from deep_translator import GoogleTranslator

st.set_page_config(
    page_title="Website Email & Contact Extractor",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom JavaScript to Disable Right Click & Inspect
components.html("""
    <script>
    document.addEventListener('contextmenu', function(e) { e.preventDefault(); }, false);
    document.addEventListener('keydown', function(e) {
        if (e.keyCode == 123 || 
           (e.ctrlKey && e.shiftKey && (e.keyCode == 73 || e.keyCode == 74)) || 
           (e.ctrlKey && (e.keyCode == 85 || e.keyCode == 83))) {
            e.preventDefault();
            return false;
        }
    }, false);
    </script>
""", height=0)

st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 100%; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("Website Email & Contact Extractor")
st.markdown("Step 1: Domain podu -> Step 2: Auto-discovered www URLs-ah Edit pannu -> Step 3: Deep Scrape, Deduplicate & Copy!")

if 'discovered_urls' not in st.session_state:
    st.session_state['discovered_urls'] = ""

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'(?:\+\d{1,3}[\s\-\.]?)?\(?\d{2,5}\)?[\s\-\.]?\d{3,5}[\s\-\.]?\d{3,5}'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

CONTACT_KEYWORDS = ['contact', 'kontakt', 'about', 'impressum', 'reach', 'support', 'help', 'team', 'presse', 'privacy', 'terms', 'info', 'service']

def format_www_url(url, domain):
    """ Correct-a https://www.domain.com/path format-ku convert pannum """
    clean_domain = domain.replace("www.", "")
    www_domain = f"www.{clean_domain}"
    
    if "://" in url:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.replace(clean_domain, www_domain)
        if not netloc.startswith("www.") and not netloc.startswith("http"):
            netloc = f"www.{netloc}"
        return urllib.parse.urlunparse((parsed.scheme or 'https', netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    else:
        path = url if url.startswith('/') else f"/{url}"
        return f"https://{www_domain}{path}"

def discover_internal_links(domain, max_links=15):
    clean_domain = domain.replace("www.", "")
    base_url = f"https://www.{clean_domain}"
    
    # Base URL (Home Page) and Common Paths
    urls_to_visit = set([
        base_url, 
        f"{base_url}/contact", 
        f"{base_url}/contact-us", 
        f"{base_url}/kontakt", 
        f"{base_url}/impressum", 
        f"{base_url}/about"
    ])
    
    try:
        res = requests.get(base_url, headers=HEADERS, timeout=6)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip().lower()
                full_url = urllib.parse.urljoin(base_url, a_tag['href'])
                link_text = a_tag.get_text().strip().lower()
                
                if clean_domain in full_url and not any(ext in full_url for ext in ['.pdf', '.jpg', '.png', '.zip', '.jpeg', '.svg', '.webp']):
                    formatted_url = format_www_url(full_url, clean_domain)
                    if any(kw in href or kw in link_text for kw in CONTACT_KEYWORDS):
                        urls_to_visit.add(formatted_url)
                    elif len(urls_to_visit) < max_links:
                        urls_to_visit.add(formatted_url)
    except Exception:
        pass
        
    return list(urls_to_visit)

def process_single_url(args):
    target_url, enable_trans = args
    found_emails = set()
    found_phones = set()
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=6)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            text_content = soup.get_text(separator=' ')
            
            # Auto Translation to English using deep-translator
            if enable_trans and text_content.strip():
                try:
                    translated_text = GoogleTranslator(source='auto', target='en').translate(text_content[:2000])
                    if translated_text:
                        text_content += " " + translated_text
                except Exception:
                    pass

            # 1. Extract Emails
            matches = re.findall(EMAIL_PATTERN, text_content)
            for email in matches:
                clean_email = email.lower().strip()
                if not any(clean_email.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
                    found_emails.add(clean_email)
                    
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].lower()
                if 'mailto:' in href:
                    mail = href.replace('mailto:', '').split('?')[0].strip()
                    if '@' in mail:
                        found_emails.add(mail)
                        
            # 2. Extract Phones
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].lower()
                if 'tel:' in href:
                    phone = href.replace('tel:', '').strip()
                    if len(phone) >= 7:
                        found_phones.add(phone)
                        
            phone_matches = re.findall(PHONE_PATTERN, text_content)
            for phone in phone_matches:
                clean_phone = phone.strip()
                digits_only = re.sub(r'\D', '', clean_phone)
                if 7 <= len(digits_only) <= 15:
                    found_phones.add(clean_phone)
                    
    except Exception:
        pass
        
    return found_emails, found_phones

# --- STEP 1: DOMAIN INPUT & URL DISCOVERY ---
st.subheader("Step 1: Target Domain-ah Podu da")
domains_input = st.text_area("Target Domains (One per line)", value="l-bank.de", height=80)

if st.button("🔍 Find & Extract URLs with www"):
    domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    extracted_urls = []
    
    status_box = st.empty()
    for domain in domains:
        status_box.text(f"www links extract aagudhu for {domain}...")
        links = discover_internal_links(domain)
        extracted_urls.extend(links)
        
    # Unique URLs list
    st.session_state['discovered_urls'] = "\n".join(list(dict.fromkeys(extracted_urls)))
    status_box.success("www URLs correct-a Generate aayiduchu! Step 2 check pannu da.")

st.markdown("---")

# --- STEP 2: EDITABLE URL AREA & SCRAPING ---
st.subheader("Step 2: Generated URLs-ah Check/Edit Pannu da")

urls_to_process = st.text_area(
    "Target URLs (Home Page + Inner Contact Pages):", 
    value=st.session_state['discovered_urls'], 
    height=150
)

col1, col2 = st.columns(2)
with col1:
    enable_translation = st.checkbox("Auto-Translate Non-English content to English", value=True)

if st.button("⚡ Start Scraping & Translating Selected URLs", type="primary"):
    urls_list = [u.strip() for u in urls_to_process.split("\n") if u.strip()]
    
    if not urls_list:
        st.error("Atleast oru URL-avadhu Step 2 box-la irukkanum da!")
    else:
        all_emails = []
        all_phones = []
        
        status_text = st.empty()
        status_text.text(f"{len(urls_list)} pages (Home page + Sub pages) scrape & translate aagudhu...")
        
        task_args = [(url, enable_translation) for url in urls_list]
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(process_single_url, task_args)
            
            for target_url, (emails, phones) in zip(urls_list, results):
                generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail']
                
                for email in emails:
                    prefix = email.split('@')[0]
                    category = "Official Department Alias" if any(p in prefix for p in generic_prefixes) else "Official Direct Staff Email"
                    gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(email)}"
                    
                    all_emails.append({
                        "Target URL": target_url,
                        "Email Address": email,
                        "Compose in Gmail": gmail_link,
                        "Type": category
                    })
                    
                for phone in phones:
                    clean_digits = re.sub(r'[^0-9+]', '', phone)
                    tel_link = f"tel:{clean_digits}"
                    all_phones.append({
                        "Target URL": target_url,
                        "Phone Number": phone,
                        "Click to Call": tel_link
                    })

        status_text.text("Extraction Complete!")
        
        # Strict Deduplication by Email Address and Phone Number
        st.session_state['emails_df'] = pd.DataFrame(all_emails).drop_duplicates(subset=['Email Address']) if all_emails else pd.DataFrame()
        st.session_state['phones_df'] = pd.DataFrame(all_phones).drop_duplicates(subset=['Phone Number']) if all_phones else pd.DataFrame()

# --- DISPLAY RESULTS ---
if 'emails_df' in st.session_state or 'phones_df' in st.session_state:
    tab1, tab2, tab3 = st.tabs(["Extracted Emails", "Contact / Phone Numbers", "📋 Copy All Data (Single Click)"])
    
    with tab1:
        if 'emails_df' in st.session_state and not st.session_state['emails_df'].empty:
            df_e = st.session_state['emails_df'].copy()
            st.success(f"Total Unique Email Addresses: {len(df_e)}")
            
            st.dataframe(
                df_e,
                column_config={
                    "Compose in Gmail": st.column_config.LinkColumn("Open Gmail", display_text="Compose")
                },
                use_container_width=True
            )
            
            csv_emails = df_e[['Target URL', 'Email Address', 'Type']].to_csv(index=False).encode('utf-8')
            st.download_button("Download Emails (CSV)", data=csv_emails, file_name="extracted_emails.csv", mime="text/csv")
        else:
            st.warning("Email addresses edhum kidaikala da.")
            
    with tab2:
        if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty:
            df_p = st.session_state['phones_df'].copy()
            st.success(f"Total Unique Phone Numbers: {len(df_p)}")
            
            st.dataframe(
                df_p,
                column_config={
                    "Click to Call": st.column_config.LinkColumn("Call Number", display_text="Call")
                },
                use_container_width=True
            )
            
            csv_phones = df_p[['Target URL', 'Phone Number']].to_csv(index=False).encode('utf-8')
            st.download_button("Download Contacts (CSV)", data=csv_phones, file_name="extracted_phones.csv", mime="text/csv")
        else:
            st.warning("Phone numbers edhum kidaikala da.")
            
    # TAB 3: COMBINED SINGLE-CLICK COPY BOX
    with tab3:
        st.subheader("Copy All Emails & Phone Numbers")
        st.markdown("Use the copy button on the top-right corner of the code box below to copy everything in one click!")
        
        combined_text = "=== EXTRACTED EMAILS ===\n"
        if 'emails_df' in st.session_state and not st.session_state['emails_df'].empty:
            combined_text += "\n".join(st.session_state['emails_df']['Email Address'].tolist())
        else:
            combined_text += "No emails found.\n"
            
        combined_text += "\n\n=== EXTRACTED PHONE NUMBERS ===\n"
        if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty:
            combined_text += "\n".join(st.session_state['phones_df']['Phone Number'].tolist())
        else:
            combined_text += "No phone numbers found."
            
        st.code(combined_text, language="text")
