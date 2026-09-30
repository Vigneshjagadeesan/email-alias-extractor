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
    page_title="Domain Specific Email Alias & Contact Extractor",
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

st.title("Domain Specific Email Alias & Contact Extractor")
st.markdown("Extract exact **`@domain.com`** official email aliases and contacts from target website pages.")

domains_input = st.text_area(
    "Enter Target Domains (One per line)", 
    value="l-bank.de", 
    height=140
)

PHONE_PATTERN = r'(?:\+\d{1,3}[\s\-\.]?)?\(?\d{2,5}\)?[\s\-\.]?\d{3,5}[\s\-\.]?\d{3,5}'

COMMON_PATHS = [
    "", "/kontakt", "/contact", "/contact-us", "/impressum", 
    "/about", "/about-us", "/presse", "/privacy", "/help", "/terms", "/team", "/en/contact.html"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

def decode_obfuscation(text):
    if not text:
        return ""
    text = urllib.parse.unquote(text)
    text = text.replace('&#64;', '@').replace('&commat;', '@').replace('%40', '@')
    text = re.sub(r'[\s\[\(]at[\s\]\)]', '@', text, flags=re.IGNORECASE)
    text = re.sub(r'[\s\[\(]dot[\s\]\)]', '.', text, flags=re.IGNORECASE)
    return text

async def fetch_page(session, url, semaphore):
    async with semaphore:
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5.0), ssl=False) as response:
                if response.status == 200:
                    return url, await response.text()
        except Exception:
            pass
        return url, ""

async def extract_from_domain(session, target_domain, semaphore):
    base_url = f"https://{target_domain}"
    found_emails, found_phones, related_domains = set(), set(), set()
    urls_to_scrape = {f"{base_url}{p}" for p in COMMON_PATHS}
    
    # Exact Dynamic Pattern for `@target_domain`
    # E.g., for l-bank.de, pattern becomes: r'[a-zA-Z0-9._%+-]+@l-bank\.de'
    clean_dom = re.escape(target_domain.replace("www.", ""))
    STRICT_ALIAS_PATTERN = r'[a-zA-Z0-9._%+-]+@' + clean_dom
    GENERIC_EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    # Discover internal sub-pages from Home Page
    _, main_html = await fetch_page(session, base_url, semaphore)
    if main_html:
        decoded_main = decode_obfuscation(main_html)
        soup = BeautifulSoup(decoded_main, 'html.parser')
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            if target_domain in parsed.netloc:
                if not any(parsed.path.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.gif', '.zip', '.css', '.js']):
                    urls_to_scrape.add(full_url)
                    if len(urls_to_scrape) >= 25:
                        break
            elif parsed.netloc and target_domain not in parsed.netloc:
                clean_netloc = parsed.netloc.replace("www.", "").strip()
                if clean_netloc and "." in clean_netloc:
                    related_domains.add(clean_netloc)

    # Scrape all discovered pages
    tasks = [fetch_page(session, u, semaphore) for u in urls_to_scrape]
    results = await asyncio.gather(*tasks)
    
    for url, raw_html in results:
        if not raw_html:
            continue
            
        html_content = decode_obfuscation(raw_html)
        soup = BeautifulSoup(html_content, 'html.parser')
        text_content = soup.get_text()
        
        # 1. First Strict Alias Extraction (`@domain.com`)
        alias_matches = re.findall(STRICT_ALIAS_PATTERN, text_content, flags=re.IGNORECASE)
        for email in alias_matches:
            clean_email = email.lower().strip().strip('.')
            found_emails.add(clean_email)
            
        # 2. General Email Extraction (All Emails on Page)
        all_matches = re.findall(GENERIC_EMAIL_PATTERN, text_content)
        for email in all_matches:
            clean_email = email.lower().strip().strip('.')
            if not any(clean_email.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.pdf']):
                found_emails.add(clean_email)
                
        for a_tag in soup.find_all('a', href=True):
            href = decode_obfuscation(a_tag['href'])
            if 'mailto:' in href:
                mail = href.replace('mailto:', '').split('?')[0].strip().lower()
                if '@' in mail:
                    found_emails.add(mail)
            elif 'tel:' in href:
                phone = href.replace('tel:', '').strip()
                if len(phone) >= 7:
                    found_phones.add(phone)
            else:
                parsed = urlparse(href)
                if parsed.netloc and target_domain not in parsed.netloc:
                    clean_netloc = parsed.netloc.replace("www.", "").strip()
                    if clean_netloc and "." in clean_netloc:
                        related_domains.add(clean_netloc)
                    
        # Phone Extraction
        phone_matches = re.findall(PHONE_PATTERN, text_content)
        for phone in phone_matches:
            clean_phone = phone.strip()
            digits_only = re.sub(r'\D', '', clean_phone)
            if 7 <= len(digits_only) <= 15:
                found_phones.add(clean_phone)
                
    return target_domain, found_emails, found_phones, related_domains

async def run_extraction(domains, progress_bar, status_text):
    all_emails, all_phones, all_related = [], [], []
    semaphore = asyncio.Semaphore(15)
    
    connector = aiohttp.TCPConnector(limit=100, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        total_domains = len(domains)
        completed = 0
        
        tasks = [extract_from_domain(session, domain, semaphore) for domain in domains]
        
        for future in asyncio.as_completed(tasks):
            domain, emails, phones, related = await future
            completed += 1
            
            progress_bar.progress(completed / total_domains)
            status_text.text(f"Extracting Data: {completed}/{total_domains} Domains Processed...")
            
            generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail']
            
            for email in emails:
                prefix = email.split('@')[0]
                if email.endswith(f"@{domain}"):
                    category = "Official Department Alias (@" + domain + ")" if any(p in prefix for p in generic_prefixes) else "Official Direct Staff Email (@" + domain + ")"
                else:
                    category = "External Email"
                    
                gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(email)}"
                all_emails.append({"Target Domain": domain, "Email Address": email, "Compose in Gmail": gmail_link, "Type": category})
                
            for phone in phones:
                clean_digits = re.sub(r'[^0-9+]', '', phone)
                all_phones.append({"Target Domain": domain, "Phone Number": phone, "Click to Call": f"tel:{clean_digits}"})
                
            for rel_dom in related:
                all_related.append({"Source Domain": domain, "Related / Linked Domain": rel_dom, "Visit Website": f"https://{rel_dom}"})
                
    return all_emails, all_phones, all_related

if st.button("Start Alias & Contact Extraction", type="primary"):
    raw_domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    domains = list(dict.fromkeys(raw_domains))
    
    if not domains:
        st.error("Please enter at least one domain!")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        all_emails, all_phones, all_related = loop.run_until_complete(run_extraction(domains, progress_bar, status_text))
        
        status_text.text("Extraction Finished Successfully!")
        
        st.session_state['emails_df'] = pd.DataFrame(all_emails).drop_duplicates(subset=['Email Address']) if all_emails else pd.DataFrame()
        st.session_state['phones_df'] = pd.DataFrame(all_phones).drop_duplicates(subset=['Phone Number']) if all_phones else pd.DataFrame()
        st.session_state['related_df'] = pd.DataFrame(all_related).drop_duplicates(subset=['Related / Linked Domain']) if all_related else pd.DataFrame()
        st.session_state['total_domains_scanned'] = len(domains)

# --- DISPLAY SECTION ---
if 'emails_df' in st.session_state or 'phones_df' in st.session_state or 'related_df' in st.session_state:
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Domains Scanned", st.session_state.get('total_domains_scanned', 0))
    col2.metric("Emails Found", len(st.session_state['emails_df']) if 'emails_df' in st.session_state and not st.session_state['emails_df'].empty else 0)
    col3.metric("Phones Found", len(st.session_state['phones_df']) if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty else 0)
    col4.metric("Related Domains", len(st.session_state['related_df']) if 'related_df' in st.session_state and not st.session_state['related_df'].empty else 0)
    
    tab1, tab2, tab3 = st.tabs(["Extracted Emails", "Contact / Phone Numbers", "🌐 Related Domains & Links"])
    
    with tab1:
        if 'emails_df' in st.session_state and not st.session_state['emails_df'].empty:
            df_e = st.session_state['emails_df'].copy()
            
            type_filter = st.selectbox("Filter Emails by Type:", ["All Emails", "Official Department Alias", "Official Direct Staff Email", "External Email"])
            
            if type_filter == "All Emails":
                filtered_df_e = df_e
            elif type_filter == "Official Department Alias":
                filtered_df_e = df_e[df_e['Type'].str.contains("Official Department Alias")]
            elif type_filter == "Official Direct Staff Email":
                filtered_df_e = df_e[df_e['Type'].str.contains("Official Direct Staff Email")]
            else:
                filtered_df_e = df_e[df_e['Type'] == "External Email"]
            
            st.dataframe(filtered_df_e, column_config={"Compose in Gmail": st.column_config.LinkColumn("Open Gmail Compose", display_text="Compose")}, use_container_width=True)
            
            st.download_button(
                label="📥 Download Extracted Emails (CSV)", 
                data=filtered_df_e[['Target Domain', 'Email Address', 'Type']].to_csv(index=False).encode('utf-8'), 
                file_name="extracted_domain_aliases.csv", 
                mime="text/csv"
            )
            
            st.markdown("---")
            st.subheader("Copy Plain Email List")
            st.code("\n".join(filtered_df_e['Email Address'].tolist()), language="text")
        else:
            st.warning("No email addresses were found.")
            
    with tab2:
        if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty:
            df_p = st.session_state['phones_df'].copy()
            
            st.dataframe(df_p, column_config={"Click to Call": st.column_config.LinkColumn("Call Number", display_text="Call")}, use_container_width=True)
            
            st.download_button(
                label="📥 Download Contact Numbers (CSV)", 
                data=df_p[['Target Domain', 'Phone Number']].to_csv(index=False).encode('utf-8'), 
                file_name="extracted_phone_numbers.csv", 
                mime="text/csv"
            )
            
            st.markdown("---")
            st.subheader("Copy Plain Phone List")
            st.code("\n".join(df_p['Phone Number'].tolist()), language="text")
        else:
            st.warning("No phone/contact numbers were found.")

    with tab3:
        if 'related_df' in st.session_state and not st.session_state['related_df'].empty:
            df_r = st.session_state['related_df'].copy()
            
            st.dataframe(df_r, column_config={"Visit Website": st.column_config.LinkColumn("Visit", display_text="Open Link")}, use_container_width=True)
            
            st.download_button(
                label="📥 Download Related Domains (CSV)", 
                data=df_r[['Source Domain', 'Related / Linked Domain']].to_csv(index=False).encode('utf-8'), 
                file_name="related_domains.csv", 
                mime="text/csv"
            )
        else:
            st.warning("No external related domains were found.")
