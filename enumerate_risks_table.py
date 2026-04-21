import pandas as pd
from itertools import product
from rule_base import Wind, Wave, Tide, Direction, compute_risk

def enumerate_risks_table():
    all_combinations = list(product(Wind, Wave, Tide, Direction))
    
    # Compute risk for each combination
    rows = []
    for w, wa, t, d in all_combinations:
        risk = compute_risk(w, wa, t, d)
        rows.append({
            "Wind": w.name,
            "Wave": wa.name,
            "Tide": t.name,
            "Direction": d.name,
            "Risk": risk["risk"]
        })
    
    # Convert to pandas DataFrame for easy viewing
    df = pd.DataFrame(rows)
    
    # Print risk counts
    print("Risk counts:")
    print(df['Risk'].value_counts())
    
    return df

def export_to_html(df, filename="enumerated_risk_table.html"):
    
    def colour_risk(val):
        if val == "LOW":
            return "background-color: #4CAF50; color: white"
        elif val == "MEDIUM":
            return "background-color: #FFC107"
        elif val == "HIGH":
            return "background-color: #FF5722; color: white"
        elif val == "VERY_HIGH":
            return "background-color: #D32F2F; color: white"
        return ""

    styled = df.style.applymap(colour_risk, subset=["Risk"])
    html = styled.to_html()
    
    with open(filename, "w") as f:
        f.write(f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial;
                    padding: 20px;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: center;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
            </style>
        </head>
        <body>
            <h2>Risk Classification Table</h2>
            {html}
        </body>
        </html>
        """)



if __name__ == "__main__":
    df = enumerate_risks_table()
    try:
        export_to_html(df)
    except Exception as e:
        print(f"ERROR! TABLE NOT CREATED: {e}")
    finally:
        print("TABLE SUCCESSFULLY CREATED")
    print(df.head())