import os
import sys

def main():
    print("Starting ASTOCK Backtesting System...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ui_path = os.path.join(script_dir, 'ui.py')
    
    # Run streamlit
    os.system(f"streamlit run {ui_path}")

if __name__ == "__main__":
    main()
