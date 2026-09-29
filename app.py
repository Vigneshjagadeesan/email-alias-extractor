import streamlit as st
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import pandas as pd
import urllib.parse
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Bulk Website Email & Contact Extractor",
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

st.title("Bulk Website Email & Contact Extractor")
st.markdown("Paste multiple domains below to extract all public Email Addresses and Phone/Contact Numbers concurrently.")

domains_input = st.text_area(
    "Enter Target Domains (One domain per line - Support Bulk Input)", 
    value="l-bank.de\napple.com\nmicrosoft.com", 
    height=180,
    help="Paste as many domains as needed, each on a new line."
)

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'(?:\+\d{1,3}[\s\-\.]?)?\(?\d{2,5}\)?[\s\-\.]?\d{3,5}[\s\-\.]?\d{3,5}'

SUB_PATHS = ["", "/contact", "/contact-us", "/kontakt", "/impressum", "/about", "/about-us", "/presse", "/privacy", "/help", "/terms"]
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

async def fetch_page(session, url, semaphore):
    async with semaphore:
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=2.0), ssl=False) as response:
                if response.status == 200:
                    return await response.text()
        except Exception:
            pass
        return ""

async def process_single_domain(session, domain, semaphore):
    found_emails, found_phones = set(), set()
    tasks = [fetch_page(session, f"https://{domain}{path}", semaphore) for path in SUB_PATHS]
    pages_html = await asyncio.gather(*tasks)
    
    for html in pages_html:
        if not html:
            continue
        soup = BeautifulSoup(html, 'html.parser')
        text_content = soup.get_text()
        
        # Extract Emails
        matches = re.findall(EMAIL_PATTERN, text_content)
        for email in matches:
            clean_email = email.lower().strip()
            if not any(clean_email.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
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
                    
        # Extract Phones
        phone_matches = re.findall(PHONE_PATTERN, text_content)
        for phone in phone_matches:
            clean_phone = phone.strip()
            digits_only = re.sub(r'\D', '', clean_phone)
            if 7 <= len(digits_only) <= 15:
                found_phones.add(clean_phone)
                
    return domain, found_emails, found_phones

async def run_bulk_extraction(domains, progress_bar, status_text):
    all_emails, all_phones = [], []
    semaphore = asyncio.Semaphore(30) # Limit concurrent connections
    
    connector = aiohttp.TCPConnector(limit=100, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        total_domains = len(domains)
        completed = 0
        
        tasks = [process_single_domain(session, domain, semaphore) for domain in domains]
        
        for future in asyncio.as_completed(tasks):
            domain, emails, phones = await future
            completed += 1
            
            # Progress Update
            progress_bar.progress(completed / total_domains)
            status_text.text(f"Scanning Bulk Domains: {completed}/{total_domains} Completed...")
            
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

if st.button("Start Bulk Extraction", type="primary"):
    raw_domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    domains = list(dict.fromkeys(raw_domains)) # Remove duplicates
    
    if not domains:
        st.error("Please enter at least one domain!")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        all_emails, all_phones = loop.run_until_complete(run_bulk_extraction(domains, progress_bar, status_text))
        
        status_text.text("Bulk Extraction Finished Successfully!")
        
        st.session_state['emails_df'] = pd.DataFrame(all_emails).drop_duplicates(subset=['Email Address']) if all_emails else pd.DataFrame()
        st.session_state['phones_df'] = pd.DataFrame(all_phones).drop_duplicates(subset=['Phone Number']) if all_phones else pd.DataFrame()
        st.session_state['total_domains_scanned'] = len(domains)

# --- DISPLAY SECTION ---
if 'emails_df' in st.session_state or 'phones_df' in st.session_state:
    st.markdown("---")
    
    # Summary Metrics
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
                label="📥 Download Bulk Emails (CSV)", 
                data=filtered_df_e[['Target Domain', 'Email Address', 'Type']].to_csv(index=False).encode('utf-8'), 
                file_name="bulk_extracted_emails.csv", 
                mime="text/csv"
            )
            
            st.markdown("---")
            st.subheader("Copy Plain Email List")
            st.code("\n".join(filtered_df_e['Email Address'].tolist()), language="text")
        else:
            st.warning("No email addresses were found across the scanned domains.")
            
    with tab2:
        if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty:
            df_p = st.session_state['phones_df'].copy()
            
            st.dataframe(df_p, column_config={"Click to Call": st.column_config.LinkColumn("Call Number", display_text="Call")}, use_container_width=True)
            
            st.download_button(
                label="📥 Download Bulk Contact Numbers (CSV)", 
                data=df_p[['Target Domain', 'Phone Number']].to_csv(index=False).encode('utf-8'), 
                file_name="bulk_extracted_phone_numbers.csv", 
                mime="text/csv"
            )
            
            st.markdown("---")
            st.subheader("Copy Plain Phone List")
            st.code("\n".join(df_p['Phone Number'].tolist()), language="text")
        else:
            st.warning("No phone/contact numbers were found across the scanned domains.")
