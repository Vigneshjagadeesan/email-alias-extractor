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
    page_title="Professional Contact Extractor",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Security Script
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

# Custom CSS to Hide Footer, Header, Profile Badge & Toolbar
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stAppDeployButton, [data-testid="stStatusWidget"], [data-testid="stDecoration"], [data-testid="stToolbar"] {
        display: none !important;
    }
    
    .main .block-container { 
        padding-top: 2rem; 
        padding-bottom: 2rem; 
        max-width: 100%; 
    }
    .stButton>button { 
        width: 100%; 
        border-radius: 8px; 
        height: 3em; 
        font-weight: bold; 
    }
    </style>
""", unsafe_allow_html=True)

st.title("🌐 Professional Email & Contact Intelligence Extractor")
st.markdown("Targeted deep web scraping with Cloudflare email decryption & auto-translation.")

if 'discovered_urls' not in st.session_state:
    st.session_state['discovered_urls'] = ""

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'(?:\+\d{1,3}[\s\-\.]?)?\(?\d{2,5}\)?[\s\-\.]?\d{3,5}[\s\-\.]?\d{3,5}'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

TARGET_CONTACT_PATHS = [
    "", "/contact", "/contact-us", "/kontakt", "/impressum", 
    "/about", "/about-us", "/despre-noi"
]

def decode_cloudflare_email(cfHex):
    try:
        r = int(cfHex[:2], 16)
        email = ''.join([chr(int(cfHex[i:i+2], 16) ^ r) for i in range(2, len(cfHex), 2)])
        return email.lower().strip()
    except Exception:
        return None

def safe_fetch_url(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
        if res.status_code == 200:
            return res
    except Exception:
        pass

    alt_url = url.replace("https://www.", "https://") if "https://www." in url else url.replace("https://", "https://www.")
    try:
        res = requests.get(alt_url, headers=HEADERS, timeout=8, allow_redirects=True)
        if res.status_code == 200:
            return res
    except Exception:
        pass

    return None

def discover_internal_links(domain):
    clean_domain = domain.replace("www.", "").strip("/")
    base_url = f"https://{clean_domain}"
    urls_to_visit = set([f"{base_url}{path}" for path in TARGET_CONTACT_PATHS])
    return list(urls_to_visit)

def process_single_url(args):
    target_url, enable_trans = args
    found_emails = set()
    found_phones = set()
    
    res = safe_fetch_url(target_url)
    if res and res.status_code == 200:
        soup = BeautifulSoup(res.text, 'html.parser')
        
        for cf_tag in soup.find_all(attrs={"data-cfemail": True}):
            hex_str = cf_tag['data-cfemail']
            decoded = decode_cloudflare_email(hex_str)
            if decoded and '@' in decoded:
                found_emails.add(decoded)
                
        for a_tag in soup.find_all('a', href=True):
            if '/cdn-cgi/l/email-protection#' in a_tag['href']:
                hex_str = a_tag['href'].split('#')[-1]
                decoded = decode_cloudflare_email(hex_str)
                if decoded and '@' in decoded:
                    found_emails.add(decoded)

        text_content = soup.get_text(separator=' ')
        
        if enable_trans and text_content.strip():
            try:
                translated_text = GoogleTranslator(source='auto', target='en').translate(text_content[:2000])
                if translated_text:
                    text_content += " " + translated_text
            except Exception:
                pass

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
                
    return found_emails, found_phones

st.subheader("1. Target Domain Input")
domains_input = st.text_area("Target Domains-ah Podu da (One per line)", value="editura-art.ro", height=80)

if st.button("🔍 Generate Contact URLs"):
    domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    extracted_urls = []
    
    for domain in domains:
        links = discover_internal_links(domain)
        extracted_urls.extend(links)
        
    st.session_state['discovered_urls'] = "\n".join(list(dict.fromkeys(extracted_urls)))
    st.success("Targeted URLs Generate aayiduchu! Step 2 check pannu da.")

st.markdown("---")

st.subheader("2. Review & Refine Target Page URLs")

urls_to_process = st.text_area(
    "Target Contact URLs to Scrape:", 
    value=st.session_state['discovered_urls'], 
    height=140
)

col1, col2 = st.columns(2)
with col1:
    enable_translation = st.checkbox("Auto-Translate Non-English content to English", value=True)

if st.button("⚡ Start Deep Extraction", type="primary"):
    urls_list = [u.strip() for u in urls_to_process.split("\n") if u.strip()]
    
    if not urls_list:
        st.error("Atleast oru URL-avadhu Step 2 box-la irukkanum da!")
    else:
        all_emails = []
        all_phones = []
        
        status_text = st.empty()
        status_text.text("Decrypting Cloudflare Protection & Scraping pages...")
        
        task_args = [(url, enable_translation) for url in urls_list]
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(process_single_url, task_args)
            
            for target_url, (emails, phones) in zip(urls_list, results):
                domain_name = urllib.parse.urlparse(target_url).netloc.replace("www.", "")
                generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail', 'comenzi', 'redactie', 'librarii']
                
                for email in emails:
                    prefix = email.split('@')[0]
                    category = "Official Department Alias" if any(p in prefix for p in generic_prefixes) else "Official Direct Staff Email"
                    gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(email)}"
                    
                    all_emails.append({
                        "Target Domain": domain_name,
                        "Email Address": email,
                        "Compose in Gmail": gmail_link,
                        "Type": category
                    })
                    
                for phone in phones:
                    clean_digits = re.sub(r'[^0-9+]', '', phone)
                    tel_link = f"tel:{clean_digits}"
                    all_phones.append({
                        "Target Domain": domain_name,
                        "Phone Number": phone,
                        "Click to Call": tel_link
                    })

        status_text.text("Extraction Complete!")
        
        st.session_state['emails_df'] = pd.DataFrame(all_emails).drop_duplicates(subset=['Email Address']) if all_emails else pd.DataFrame()
        st.session_state['phones_df'] = pd.DataFrame(all_phones).drop_duplicates(subset=['Phone Number']) if all_phones else pd.DataFrame()

if 'emails_df' in st.session_state or 'phones_df' in st.session_state:
    st.markdown("---")
    st.subheader("3. Extraction Results")
    
    tab1, tab2 = st.tabs(["📧 Extracted Emails", "📞 Contact Numbers"])
    
    with tab1:
        if 'emails_df' in st.session_state and not st.session_state['emails_df'].empty:
            df_e = st.session_state['emails_df'].copy()
            st.success(f"Total Unique Emails Found: {len(df_e)}")
            
            st.dataframe(
                df_e,
                column_config={
                    "Compose in Gmail": st.column_config.LinkColumn("Open Gmail", display_text="Compose")
                },
                use_container_width=True
            )
            
            st.markdown("#### Quick Copy Plain Emails")
            email_text = "\n".join(df_e['Email Address'].tolist())
            st.code(email_text, language="text")
            
            csv_emails = df_e[['Target Domain', 'Email Address', 'Type']].to_csv(index=False).encode('utf-8')
            st.download_button("Download Emails CSV", data=csv_emails, file_name="extracted_emails.csv", mime="text/csv")
        else:
            st.warning("Email addresses edhum kidaikala da.")
            
    with tab2:
        if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty:
            df_p = st.session_state['phones_df'].copy()
            st.success(f"Total Unique Contact Numbers Found: {len(df_p)}")
            
            st.dataframe(
                df_p,
                column_config={
                    "Click to Call": st.column_config.LinkColumn("Call Number", display_text="Call")
                },
                use_container_width=True
            )
            
            st.markdown("#### Quick Copy Plain Phone Numbers")
            phone_text = "\n".join(df_p['Phone Number'].tolist())
            st.code(phone_text, language="text")
            
            csv_phones = df_p[['Target Domain', 'Phone Number']].to_csv(index=False).encode('utf-8')
            st.download_button("Download Contacts CSV", data=csv_phones, file_name="extracted_phones.csv", mime="text/csv")
        else:
            st.warning("Phone numbers edhum kidaikala da.")
