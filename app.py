import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Ultra-Fast Email & Contact Extractor", page_icon="⚡", layout="wide")

st.title("⚡ Ultra-Fast Email & Contact Number Extractor")
st.markdown("Extract ALL public Email Addresses and Phone/Contact Numbers found on target website pages at high speed.")

domains_input = st.text_area("Enter Target Domains (One per line)", value="l-bank.de", height=120)

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'(?:\+\d{1,3}[\s\-\.]?)?\(?\d{2,5}\)?[\s\-\.]?\d{3,5}[\s\-\.]?\d{3,5}'

SUB_PATHS = [
    "", "/contact", "/contact-us", "/kontakt", "/impressum", 
    "/about", "/about-us", "/presse", "/privacy", "/help", "/terms"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_and_extract_data(args):
    domain, path = args
    target_url = f"https://{domain}{path}"
    found_emails = set()
    found_phones = set()
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=3)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            text_content = soup.get_text()
            
            # 1. Extract Emails
            matches = re.findall(EMAIL_PATTERN, text_content)
            for email in matches:
                clean_email = email.lower().strip()
                if not any(clean_email.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
                    found_emails.add(clean_email)
                
            for a_tag in soup.find_all('a', href=True):
                if 'mailto:' in a_tag['href']:
                    mail = a_tag['href'].replace('mailto:', '').split('?')[0].strip().lower()
                    if '@' in mail:
                        found_emails.add(mail)
                        
            # 2. Extract Phone Numbers
            for a_tag in soup.find_all('a', href=True):
                if 'tel:' in a_tag['href']:
                    phone = a_tag['href'].replace('tel:', '').strip()
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

if st.button("Start Extraction", type="primary"):
    domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    
    all_emails = []
    all_phones = []
    
    status_text = st.empty()
    status_text.text("Scanning website pages at high speed...")
    
    for domain in domains:
        tasks = [(domain, path) for path in SUB_PATHS]
        
        domain_emails = set()
        domain_phones = set()
        
        with ThreadPoolExecutor(max_workers=15) as executor:
            results = executor.map(fetch_and_extract_data, tasks)
            for emails, phones in results:
                domain_emails.update(emails)
                domain_phones.update(phones)
                
        generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail']
        
        # Email Classification
        for email in domain_emails:
            prefix = email.split('@')[0]
            if email.endswith(f"@{domain}"):
                category = "Official Department Alias" if any(p in prefix for p in generic_prefixes) else "Official Direct Staff Email"
            else:
                category = "External / Other Email"
                
            all_emails.append({
                "Target Domain": domain,
                "Email Address": email,
                "Type": category
            })
            
        # Phone Numbers
        for phone in domain_phones:
            all_phones.append({
                "Target Domain": domain,
                "Phone Number": phone
            })

    status_text.text("Extraction Complete!")
    
    st.session_state['emails_df'] = pd.DataFrame(all_emails).drop_duplicates(subset=['Email Address']) if all_emails else pd.DataFrame()
    st.session_state['phones_df'] = pd.DataFrame(all_phones).drop_duplicates(subset=['Phone Number']) if all_phones else pd.DataFrame()

# --- DISPLAY TABS & DOWNLOAD SECTION ---
if 'emails_df' in st.session_state or 'phones_df' in st.session_state:
    
    tab1, tab2 = st.tabs(["📧 Extracted Emails", "📞 Contact / Phone Numbers"])
    
    # EMAIL TAB
    with tab1:
        if 'emails_df' in st.session_state and not st.session_state['emails_df'].empty:
            df_e = st.session_state['emails_df']
            st.success(f"Found {len(df_e)} total email addresses!")
            
            type_filter = st.selectbox("Filter Emails:", ["All Emails", "Official Department Alias", "Official Direct Staff Email", "External / Other Email"])
            filtered_df_e = df_e if type_filter == "All Emails" else df_e[df_e['Type'] == type_filter]
            
            st.dataframe(filtered_df_e, use_container_width=True)
            
            # Download Email Button
            csv_emails = filtered_df_e.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Extracted Emails as CSV",
                data=csv_emails,
                file_name="extracted_emails.csv",
                mime="text/csv",
                type="secondary"
            )
            
            st.markdown("---")
            st.subheader("📋 Copy Email List")
            email_list_str = "\n".join(filtered_df_e['Email Address'].tolist())
            st.code(email_list_str, language="text")
        else:
            st.warning("No email addresses were found.")
            
    # PHONE TAB
    with tab2:
        if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty:
            df_p = st.session_state['phones_df']
            st.success(f"Found {len(df_p)} total phone/contact numbers!")
            
            st.dataframe(df_p, use_container_width=True)
            
            # Download Phone Button
            csv_phones = df_p.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Contact Numbers as CSV",
                data=csv_phones,
                file_name="extracted_phone_numbers.csv",
                mime="text/csv",
                type="secondary"
            )
            
            st.markdown("---")
            st.subheader("📋 Copy Phone List")
            phone_list_str = "\n".join(df_p['Phone Number'].tolist())
            st.code(phone_list_str, language="text")
        else:
            st.warning("No phone/contact numbers were found on the website pages.")
