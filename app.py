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

# Custom JavaScript
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
st.markdown("Deep scrape domains and direct contact URLs, auto-discover links, translate foreign languages to English, and extract contacts!")

# Dual Input Section
st.subheader("1. Enter Domains or Specific Links")
col_input1, col_input2 = st.columns(2)

with col_input1:
    domains_input = st.text_area("Target Domains (One per line)", value="l-bank.de", height=120, help="Enter main domains like: example.com")

with col_input2:
    direct_urls_input = st.text_area("Direct Page URLs (One per line)", value="https://www.l-bank.de/kontakt", height=120, help="Enter full page links like: https://example.com/contact")

# Options Section
col1, col2 = st.columns(2)
with col1:
    enable_translation = st.checkbox("Auto-Translate Non-English content to English", value=True)
with col2:
    max_depth_links = st.slider("Max Links to Auto-Discover per domain", min_value=5, max_value=30, value=20)

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'(?:\+\d{1,3}[\s\-\.]?)?\(?\d{2,5}\)?[\s\-\.]?\d{3,5}[\s\-\.]?\d{3,5}'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

CONTACT_KEYWORDS = ['contact', 'kontakt', 'about', 'impressum', 'reach', 'support', 'help', 'team', 'presse', 'privacy', 'terms', 'info', 'service']

def discover_internal_links(domain, max_links=20):
    """ Deep crawls homepage and extracts all contact-related internal sub-links """
    base_url = f"https://{domain}"
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
                
                if domain in full_url and not any(ext in full_url for ext in ['.pdf', '.jpg', '.png', '.zip', '.jpeg', '.svg', '.webp']):
                    if any(kw in href or kw in link_text for kw in CONTACT_KEYWORDS):
                        urls_to_visit.add(full_url)
                    elif len(urls_to_visit) < max_links:
                        urls_to_visit.add(full_url)
    except Exception:
        pass
        
    return list(urls_to_visit)

def process_single_url(target_url):
    """ Scrapes a single URL, translates text if needed, and extracts emails & phones """
    found_emails = set()
    found_phones = set()
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=6)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            text_content = soup.get_text(separator=' ')
            
            # Auto Translation to English using deep-translator
            if enable_translation and text_content.strip():
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

if st.button("Start Deep Crawl & Extraction", type="primary"):
    # Parse Domains & Direct URLs
    domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    direct_urls = [u.strip() for u in direct_urls_input.split("\n") if u.strip()]
    
    # Ensure direct URLs start with http/https
    formatted_direct_urls = []
    for url in direct_urls:
        if not url.startswith("http://") and not url.startswith("https://"):
            formatted_direct_urls.append(f"https://{url}")
        else:
            formatted_direct_urls.append(url)

    all_emails = []
    all_phones = []
    
    status_text = st.empty()
    
    # Process Domains (Auto-Discover Internal Links)
    for domain in domains:
        status_text.text(f"🔍 Crawling and discovering links for domain: {domain}...")
        
        urls_to_scrape = discover_internal_links(domain, max_links=max_depth_links)
        
        status_text.text(f"⚡ Scraping & Translating {len(urls_to_scrape)} pages for {domain}...")
        
        domain_emails = set()
        domain_phones = set()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(process_single_url, urls_to_scrape)
            for emails, phones in results:
                domain_emails.update(emails)
                domain_phones.update(phones)
                
        generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail']
        
        for email in domain_emails:
            prefix = email.split('@')[0]
            if domain in email:
                category = "Official Department Alias" if any(p in prefix for p in generic_prefixes) else "Official Direct Staff Email"
            else:
                category = "External / Other Email"
                
            gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(email)}"
            
            all_emails.append({
                "Target Domain / URL": domain,
                "Email Address": email,
                "Compose in Gmail": gmail_link,
                "Type": category
            })
            
        for phone in domain_phones:
            clean_digits = re.sub(r'[^0-9+]', '', phone)
            tel_link = f"tel:{clean_digits}"
            all_phones.append({
                "Target Domain / URL": domain,
                "Phone Number": phone,
                "Click to Call": tel_link
            })

    # Process Direct URLs Input Box
    if formatted_direct_urls:
        status_text.text(f"⚡ Scraping & Translating {len(formatted_direct_urls)} Direct Page Links...")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(process_single_url, formatted_direct_urls)
            for target_url, (emails, phones) in zip(formatted_direct_urls, results):
                domain_name = urllib.parse.urlparse(target_url).netloc
                
                for email in emails:
                    prefix = email.split('@')[0]
                    category = "Official Direct Staff Email" if domain_name in email else "External / Other Email"
                    gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(email)}"
                    
                    all_emails.append({
                        "Target Domain / URL": target_url,
                        "Email Address": email,
                        "Compose in Gmail": gmail_link,
                        "Type": category
                    })
                    
                for phone in phones:
                    clean_digits = re.sub(r'[^0-9+]', '', phone)
                    tel_link = f"tel:{clean_digits}"
                    all_phones.append({
                        "Target Domain / URL": target_url,
                        "Phone Number": phone,
                        "Click to Call": tel_link
                    })

    status_text.text("Extraction Complete!")
    
    st.session_state['emails_df'] = pd.DataFrame(all_emails).drop_duplicates(subset=['Email Address']) if all_emails else pd.DataFrame()
    st.session_state['phones_df'] = pd.DataFrame(all_phones).drop_duplicates(subset=['Phone Number']) if all_phones else pd.DataFrame()

# --- DISPLAY RESULTS ---
if 'emails_df' in st.session_state or 'phones_df' in st.session_state:
    tab1, tab2 = st.tabs(["Extracted Emails", "Contact / Phone Numbers"])
    
    with tab1:
        if 'emails_df' in st.session_state and not st.session_state['emails_df'].empty:
            df_e = st.session_state['emails_df'].copy()
            st.success(f"Found {len(df_e)} total email addresses!")
            
            type_filter = st.selectbox("Filter Emails:", ["All Emails", "Official Department Alias", "Official Direct Staff Email", "External / Other Email"])
            filtered_df_e = df_e if type_filter == "All Emails" else df_e[df_e['Type'] == type_filter]
            
            st.dataframe(
                filtered_df_e,
                column_config={
                    "Compose in Gmail": st.column_config.LinkColumn(
                        "Open Gmail Compose",
                        display_text="Compose"
                    )
                },
                use_container_width=True
            )
            
            csv_emails = filtered_df_e[['Target Domain / URL', 'Email Address', 'Type']].to_csv(index=False).encode('utf-8')
            st.download_button("Download Extracted Emails (CSV)", data=csv_emails, file_name="extracted_emails.csv", mime="text/csv")
        else:
            st.warning("No email addresses found.")
            
    with tab2:
        if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty:
            df_p = st.session_state['phones_df'].copy()
            st.success(f"Found {len(df_p)} total phone numbers!")
            
            st.dataframe(
                df_p,
                column_config={
                    "Click to Call": st.column_config.LinkColumn(
                        "Call Number",
                        display_text="Call"
                    )
                },
                use_container_width=True
            )
            
            csv_phones = df_p[['Target Domain / URL', 'Phone Number']].to_csv(index=False).encode('utf-8')
            st.download_button("Download Contact Numbers (CSV)", data=csv_phones, file_name="extracted_phones.csv", mime="text/csv")
        else:
            st.warning("No phone numbers found.")
