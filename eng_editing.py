import streamlit as st
import sqlite3
import pandas as pd

def get_db_connection():
    """Connect to the SQLite database."""
    conn = sqlite3.connect('veterinary_consultations.db')
    return conn

def fetch_consultations():
    """Fetch all consultations from the database."""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM consultations", conn)
    conn.close()
    return df

def delete_consultation(consultation_id):
    """Delete a consultation from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM consultations WHERE id = ?", (consultation_id,))
    conn.commit()
    conn.close()

def update_consultation(consultation_id, data):
    """Update a consultation in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE consultations
        SET date = ?, veterinarian_name = ?, owner_name = ?, owner_phone = ?, 
            pet_name = ?, pet_breed = ?, pet_age = ?, symptoms = ?, 
            examinations = ?, recommendations = ?, diagnostics = ?
        WHERE id = ?
    ''', (
        data['date'],
        data['veterinarian_name'],
        data['owner_name'],
        data['owner_phone'],
        data['pet_name'],
        data['pet_breed'],
        data['pet_age'],
        data['symptoms'],
        data['examinations'],
        data['recommendations'],
        data['diagnostics'],
        consultation_id
    ))
    conn.commit()
    conn.close()

def main():
    st.title("🐾 Veterinary Consultation Management")
    
    tabs = ["📋 View Records", "✏️ Edit Record", "🗑️ Delete Record"]
    selected_tab = st.tabs(tabs)
    
    # View Records Tab
    with selected_tab[0]:
        st.subheader("Consultation Records 📊")
        df = fetch_consultations()
        
        # Search functionality
        search_term = st.text_input("🔍 Search Records", 
            placeholder="Search by pet name, owner name, or symptoms...")
        
        if search_term:
            filtered_df = df[df.apply(lambda row: row.astype(str).str.contains(
                search_term, case=False).any(), axis=1)]
            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.dataframe(df, use_container_width=True)
    
    # Edit Record Tab
    with selected_tab[1]:
        st.subheader("Edit Consultation Record ✏️")
        df = fetch_consultations()
        
        if not df.empty:
            consultation_id = st.selectbox(
                "Select Record to Edit", 
                df['id'].tolist(),
                format_func=lambda x: f"Record #{x} - {df[df['id'] == x]['pet_name'].iloc[0]}"
            )
            
            if consultation_id:
                consultation_data = df[df['id'] == consultation_id].iloc[0]
                
                with st.form("edit_consultation_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_data = {
                            'date': st.date_input("Date 🗓️", 
                                pd.to_datetime(consultation_data['date'])),
                            'veterinarian_name': st.text_input("Veterinarian Name 🩺", 
                                value=consultation_data['veterinarian_name']),
                            'owner_name': st.text_input("Owner Name 👤", 
                                value=consultation_data['owner_name']),
                            'owner_phone': st.text_input("Owner Phone 📞", 
                                value=consultation_data['owner_phone']),
                            'pet_name': st.text_input("Pet Name 🐕", 
                                value=consultation_data['pet_name']),
                            'pet_breed': st.text_input("Pet Breed 🐈", 
                                value=consultation_data['pet_breed'])
                        }
                    
                    with col2:
                        new_data.update({
                            'pet_age': st.number_input("Pet Age (years) 🎂", 
                                value=float(consultation_data['pet_age']), 
                                min_value=0.0, step=0.1),
                            'symptoms': st.text_area("Symptoms 🩹", 
                                value=consultation_data['symptoms']),
                            'examinations': st.text_area("Examinations 🔬", 
                                value=consultation_data['examinations']),
                            'recommendations': st.text_area("Recommendations 💡", 
                                value=consultation_data['recommendations']),
                            'diagnostics': st.text_area("Diagnostics 🧪", 
                                value=consultation_data['diagnostics'])
                        })
                    
                    submit_button = st.form_submit_button("Update Record ✅")
                    
                    if submit_button:
                        new_data['date'] = new_data['date'].strftime('%Y-%m-%d')
                        update_consultation(consultation_id, new_data)
                        st.success("Record updated successfully! 🎉")
                        st.rerun()
        else:
            st.info("No records available to edit.")
    
    # Delete Record Tab
    with selected_tab[2]:
        st.subheader("Delete Consultation Record 🗑️")
        df = fetch_consultations()
        
        if not df.empty:
            consultation_id = st.selectbox(
                "Select Record to Delete", 
                df['id'].tolist(),
                format_func=lambda x: f"Record #{x} - {df[df['id'] == x]['pet_name'].iloc[0]}"
            )
            
            if consultation_id:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Delete Record ❌"):
                        delete_consultation(consultation_id)
                        st.success("Record deleted successfully! 🗑️")
                        st.rerun()
        else:
            st.info("No records available to delete.")

if __name__ == '__main__':
    main()