import streamlit as st
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import pandas as pd
import urllib.parse
from urllib.parse import urlparse, urljoin
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Deep Website Email & Contact Extractor",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Disable Right Click & Inspect Shortcuts
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
    .main .block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; max-width: 100%; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.2em; font-weight: bold; font-size: 16px; }
    </style>
""", unsafe_allow_html=True)

st.title("Deep Website Email & Contact Extractor")
st.markdown("Deep crawl target websites to extract ALL public email addresses and phone numbers across internal pages.")

domains_input = st.text_area(
    "Enter Target Domains (One per line - Deep Crawl Enabled)", 
    value="l-bank.de", 
    height=140,
    help="Enter domain names. The tool will automatically discover internal sub-pages and scrape all emails."
)

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'(?:\+\d{1,3}[\s\-\.]?)?\(?\d{2,5}\)?[\s\-\.]?\d{3,5}[\s\-\.]?\d{3,5}'

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

async def fetch(session, url, semaphore):
    async with semaphore:
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=2.5), ssl=False) as response:
                if response.status == 200:
                    text = await response.text()
                    return url, text
        except Exception:
            pass
        return url, ""

async def crawl_and_extract_domain(session, domain, semaphore):
    base_url = f"https://{domain}"
    found_emails, found_phones = set(), set()
    internal_links = {base_url}
    
    # 1. Fetch Main Page to Discover Sub-Links
    _, main_html = await fetch(session, base_url, semaphore)
    if main_html:
        soup = BeautifulSoup(main_html, 'html.parser')
        
        # Discover internal pages from <a> tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            # Keep only same-domain internal pages
            if parsed.netloc == domain or parsed.netloc == f"www.{domain}":
                # Filter out asset files
                if not any(parsed.path.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.gif', '.zip', '.css', '.js']):
                    internal_links.add(full_url)
                    if len(internal_links) >= 20: # Limit max internal sub-pages per domain for speed
                        break

    # 2. Concurrently Fetch All Discovered Pages
    tasks = [fetch(session, url, semaphore) for url in internal_links]
    results = await asyncio.gather(*tasks)
    
    for _, html in results:
        if not html:
            continue
        soup = BeautifulSoup(html, 'html.parser')
        text_content = soup.get_text()
        
        # Email Extraction (Plain Text & Mailto Links)
        matches = re.findall(EMAIL_PATTERN, text_content)
        for email in matches:
            clean_email = email.lower().strip()
            if not any(clean_email.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.pdf']):
                found_emails.add(clean_email)
                
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if 'mailto:' in href:
                mail = href.replace('mailto:', '').split('?')[0].strip().lower()
                if '@' in mail:
                    found_emails.add(mail)
            elif 'tel:' in href:
                phone = href.replace('tel:', '').strip()
                if len(phone) >= 7:
                    found_phones.add(phone)
                    
        # Phone Extraction
        phone_matches = re.findall(PHONE_PATTERN, text_content)
        for phone in phone_matches:
            clean_phone = phone.strip()
            digits_only = re.sub(r'\D', '', clean_phone)
            if 7 <= len(digits_only) <= 15:
                found_phones.add(clean_phone)
                
    return domain, found_emails, found_phones

async def run_deep_extraction(domains, progress_bar, status_text):
    all_emails, all_phones = [], []
    semaphore = asyncio.Semaphore(25)
    
    connector = aiohttp.TCPConnector(limit=100, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        total_domains = len(domains)
        completed = 0
        
        tasks = [crawl_and_extract_domain(session, domain, semaphore) for domain in domains]
        
        for future in asyncio.as_completed(tasks):
            domain, emails, phones = await future
            completed += 1
            
            progress_bar.progress(completed / total_domains)
            status_text.text(f"Deep Crawling Domains: {completed}/{total_domains} Completed...")
            
            generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail']
            
            for email in emails:
                prefix = email.split('@')[0]
                category = "Official Department Alias" if (email.endswith(f"@{domain}") and any(p in prefix for p in generic_prefixes)) else ("Official Direct Staff Email" if email.endswith(f"@{domain}") else "External / Other Email")
                gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(email)}"
                all_emails.append({"Target Domain": domain, "Email Address": email, "Compose in Gmail": gmail_link, "Type": category})
                
            for phone in phones:
                clean_digits = re.sub(r'[^0-9+]', '', phone)
                all_phones.append({"Target Domain": domain, "Phone Number": phone, "Click to Call": f"tel:{clean_digits}"})
                
    return all_emails, all_phones

if st.button("Start Deep Crawl & Extraction", type="primary"):
    raw_domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    domains = list(dict.fromkeys(raw_domains))
    
    if not domains:
        st.error("Please enter at least one domain!")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        all_emails, all_phones = loop.run_until_complete(run_deep_extraction(domains, progress_bar, status_text))
        
        status_text.text("Deep Extraction Completed Successfully!")
        
        st.session_state['emails_df'] = pd.DataFrame(all_emails).drop_duplicates(subset=['Email Address']) if all_emails else pd.DataFrame()
        st.session_state['phones_df'] = pd.DataFrame(all_phones).drop_duplicates(subset=['Phone Number']) if all_phones else pd.DataFrame()
        st.session_state['total_domains_scanned'] = len(domains)

# --- DISPLAY SECTION ---
if 'emails_df' in st.session_state or 'phones_df' in st.session_state:
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Domains Scanned", st.session_state.get('total_domains_scanned', 0))
    col2.metric("Total Emails Found", len(st.session_state['emails_df']) if 'emails_df' in st.session_state and not st.session_state['emails_df'].empty else 0)
    col3.metric("Total Phone Numbers Found", len(st.session_state['phones_df']) if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty else 0)
    
    tab1, tab2 = st.tabs(["Extracted Emails", "Contact / Phone Numbers"])
    
    with tab1:
        if 'emails_df' in st.session_state and not st.session_state['emails_df'].empty:
            df_e = st.session_state['emails_df'].copy()
            
            type_filter = st.selectbox("Filter Emails by Type:", ["All Emails", "Official Department Alias", "Official Direct Staff Email", "External / Other Email"])
            filtered_df_e = df_e if type_filter == "All Emails" else df_e[df_e['Type'] == type_filter]
            
            st.dataframe(filtered_df_e, column_config={"Compose in Gmail": st.column_config.LinkColumn("Open Gmail Compose", display_text="Compose")}, use_container_width=True)
            
            st.download_button(
                label="📥 Download Extracted Emails (CSV)", 
                data=filtered_df_e[['Target Domain', 'Email Address', 'Type']].to_csv(index=False).encode('utf-8'), 
                file_name="deep_extracted_emails.csv", 
                mime="text/csv"
            )
            
            st.markdown("---")
            st.subheader("Copy Plain Email List")
            st.code("\n".join(filtered_df_e['Email Address'].tolist()), language="text")
        else:
            st.warning("No email addresses were found across the crawled website pages.")
            
    with tab2:
        if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty:
            df_p = st.session_state['phones_df'].copy()
            
            st.dataframe(df_p, column_config={"Click to Call": st.column_config.LinkColumn("Call Number", display_text="Call")}, use_container_width=True)
            
            st.download_button(
                label="📥 Download Contact Numbers (CSV)", 
                data=df_p[['Target Domain', 'Phone Number']].to_csv(index=False).encode('utf-8'), 
                file_name="deep_extracted_phone_numbers.csv", 
                mime="text/csv"
            )
            
            st.markdown("---")
            st.subheader("Copy Plain Phone List")
            st.code("\n".join(df_p['Phone Number'].tolist()), language="text")
        else:
            st.warning("No phone/contact numbers were found across the crawled website pages.")
