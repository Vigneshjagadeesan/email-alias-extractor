import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time

st.set_page_config(page_title="Direct Email Alias Extractor", page_icon="🔍", layout="wide")

st.title("🔍 Direct Domain Email Alias Extractor")
st.markdown("Extract official department aliases directly from target website pages with filter & copy options.")

domains_input = st.text_area("Enter Target Domains (One per line)", value="l-bank.de", height=120)

def extract_emails_from_text(text):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return set(re.findall(email_pattern, text))

if st.button("Start Direct Extraction", type="primary"):
    domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    all_results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    sub_paths = ["", "/contact", "/kontakt", "/impressum", "/about", "/about-us", "/presse"]

    for idx, domain in enumerate(domains):
        status_text.text(f"Scanning pages for: {domain} ...")
        found_emails = set()
        
        for path in sub_paths:
            target_url = f"https://{domain}{path}"
            try:
                res = requests.get(target_url, headers=headers, timeout=8)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    
                    extracted = extract_emails_from_text(soup.get_text())
                    
                    for a_tag in soup.find_all('a', href=True):
                        if 'mailto:' in a_tag['href']:
                            mail = a_tag['href'].replace('mailto:', '').split('?')[0].strip()
                            if '@' in mail:
                                extracted.add(mail)
                                
                    for email in extracted:
                        email_clean = email.lower().strip()
                        if email_clean.endswith(f"@{domain}"):
                            found_emails.add(email_clean)
            except Exception:
                continue

        generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail']
        
        for email in found_emails:
            prefix = email.split('@')[0]
            category = "Department Alias" if any(p in prefix for p in generic_prefixes) else "Direct Staff Email"
            
            all_results.append({
                "Domain": domain,
                "Email Address": email,
                "Category": category
            })
            
        progress_bar.progress((idx + 1) / len(domains))
        time.sleep(0.5)

    status_text.text("Extraction Complete!")
    
    if all_results:
        df = pd.DataFrame(all_results).drop_duplicates(subset=['Email Address'])
        st.session_state['extracted_df'] = df
    else:
        st.session_state['extracted_df'] = pd.DataFrame()
        st.warning("No public email aliases were found on the website pages for the given domain.")

# --- DISPLAY RESULTS & COPY SECTION ---
if 'extracted_df' in st.session_state and not st.session_state['extracted_df'].empty:
    df = st.session_state['extracted_df']
    
    st.success(f"Successfully found {len(df)} unique email addresses!")
    
    # Filter Option
    col1, col2 = st.columns([1, 2])
    with col1:
        category_filter = st.selectbox("Filter Category:", ["All Emails", "Department Alias", "Direct Staff Email"])
    
    filtered_df = df if category_filter == "All Emails" else df[df['Category'] == category_filter]
    
    # Display Table
    st.dataframe(filtered_df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("📋 Separated Email List (Ready to Copy)")
    
    # Clean list for single-click copy
    email_list_str = "\n".join(filtered_df['Email Address'].tolist())
    
    # Display in a Code Box with Built-in Copy Button
    st.code(email_list_str, language="text")
    
    # Download Button
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Filtered Results as CSV",
        data=csv_data,
        file_name="extracted_aliases.csv",
        mime="text/csv"
    )