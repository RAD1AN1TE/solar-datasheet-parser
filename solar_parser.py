import boto3
import json
import argparse
import sys
import os
import pdfplumber
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# Global Constants from Requirements
AWS_REGION = "us-west-2"
MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"

# Start of JSON Schema for Prompt
JSON_SCHEMA = """
{
  "product": {
    "manufacturer": "string",
    "series": "string",
    "model_types": ["string"],
    "wattage_range": { "min": number, "max": number }
  },
  "electrical_specs": {
    "power_variants": [
      {
        "nominal_power_w": number,
        "vmax_v": number,
        "imax_a": number,
        "voc_v": number,
        "isc_a": number,
        "efficiency_pct": number
      }
    ],
    "max_system_voltage_v": number,
    "max_series_fuse_a": number
  },
  "mechanical_specs": {
    "length_mm": number,
    "width_mm": number,
    "weight_kg": number,
    "frame_material": "string",
    "cell_type": "string"
  },
  "temperature_specs": {
    "operating_range_c": { "min": number, "max": number },
    "temp_coefficient_pmax_pct_per_c": number,
    "noct_c": number
  },
  "warranty": {
    "years": number,
    "degradation_rate_pct": number
  },
  "certifications": ["string"]
}
"""

def extract_text_from_pdf(pdf_path):
    """Extracts text content from a PDF file using pdfplumber."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}", file=sys.stderr)
        sys.exit(1)
    return text

def parse_with_bedrock(text):
    """Sends the text to AWS Bedrock (Claude) to extract structured data."""
    
    prompt = f"""
    You are an expert data extraction assistant. Extract technical specifications from the datasheet text and output EXACTLY one JSON object that matches the schema.

    <datasheet_text>
    {text}
    </datasheet_text>

    Rules (must follow):
    1) Output ONLY valid JSON (no markdown, no commentary).
    2) Use EXACTLY these top-level keys and nesting:
       product, electrical_specs, mechanical_specs, temperature_specs, warranty, certifications
    3) Do NOT invent values. If a value is not explicitly present, use null.
    4) All numeric fields must be numbers (no units, no percent sign). Examples:
       - "34 kg" -> 34
       - "0.3%" -> 0.3
       - "1,500 V" -> 1500
       - "-0.32 %/°C" -> -0.32
    5) model_types must include only identifiers explicitly found (do not infer).
    6) certifications: include exact strings as written, including versions/years if present.
    7) electrical_specs.power_variants: include one object for EACH power class/column/variant in the datasheet. Each object must include all 6 fields; if a field for that variant is missing, set it to null.
    8) wattage_range.min/max must be derived from the power_variants nominal_power_w values when possible; otherwise null.

    Schema (types + keys must match exactly):
    {JSON_SCHEMA}
    """

    client = boto3.client(
        service_name='bedrock-runtime',
        region_name=AWS_REGION
    )

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0
    })

    try:
        response = client.invoke_model(
            modelId=MODEL_ID,
            body=body
        )
        
        response_body = json.loads(response.get('body').read())
        result_text = response_body.get('content')[0].get('text')
        
        # Attempt to clean up if the model wrapped it in markdown code blocks despite instructions
        clean_json_text = result_text.strip()
        if clean_json_text.startswith("```json"):
            clean_json_text = clean_json_text[7:]
        if clean_json_text.endswith("```"):
            clean_json_text = clean_json_text[:-3]
            
        return json.loads(clean_json_text)

    except ClientError as e:
        print(f"AWS Bedrock API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response from model: {e}", file=sys.stderr)
        print("Raw response:", result_text, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


def generate_summary(data):
    """Generates a human-readable summary from the extracted JSON data."""
    try:
        product = data.get("product", {})
        elec = data.get("electrical_specs", {})
        mech = data.get("mechanical_specs", {})
        temp = data.get("temperature_specs", {})
        warranty = data.get("warranty", {})
        
        # Determine max power
        max_power = "N/A"
        if product.get("wattage_range"):
             max_power = f"{product['wattage_range'].get('max')}W"
        
        # Calculate max efficiency safely
        efficiency_values = [v.get('efficiency_pct') for v in elec.get('power_variants', []) if v.get('efficiency_pct') is not None]
        max_efficiency = max(efficiency_values) if efficiency_values else "N/A"

        summary = f"""
## Product Overview
**{product.get('manufacturer', 'Unknown')} {product.get('series', 'Solar Module')}**
*Models*: {', '.join(product.get('model_types', []))}
*Power Range*: {product.get('wattage_range', {}).get('min')}W - {product.get('wattage_range', {}).get('max')}W

## Key Specifications
- **Efficiency**: Up to {max_efficiency}%
- **Max System Voltage**: {elec.get('max_system_voltage_v')}V
- **Dimensions**: {mech.get('length_mm')}mm x {mech.get('width_mm')}mm
- **Weight**: {mech.get('weight_kg')}kg
- **Cell Type**: {mech.get('cell_type')}

## Performance & Warranty
- **Operating Temp**: {temp.get('operating_range_c', {}).get('min')}°C to {temp.get('operating_range_c', {}).get('max')}°C
- **Temperature Coefficient (Pmax)**: {temp.get('temp_coefficient_pmax_pct_per_c')}%/°C
- **Warranty**: {warranty.get('years')} Years ({warranty.get('degradation_rate_pct')}% degradation/year)
"""
        return summary
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def process_pdf(pdf_path):
    """Refactored main logic to be callable from app.py"""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")
        
    text_content = extract_text_from_pdf(pdf_path)
    text_content = extract_text_from_pdf(pdf_path)
    raw_json = parse_with_bedrock(text_content)
    
    # Enforce Key Order
    ordered_keys = [
        "product", 
        "electrical_specs", 
        "mechanical_specs", 
        "temperature_specs", 
        "warranty", 
        "certifications"
    ]
    json_output = {k: raw_json.get(k) for k in ordered_keys if k in raw_json}
    
    summary = generate_summary(json_output)
    
    return json_output, summary

def main():
    parser = argparse.ArgumentParser(description="Extract solar module specs from PDF using AWS Bedrock.")
    parser.add_argument("pdf_path", help="Path to the PDF datasheet file")
    parser.add_argument("--output", "-o", help="Path to save the output JSON file", default="output.json")
    
    args = parser.parse_args()
    
    try:
        print(f"Extracting text from {args.pdf_path}...")
        json_output, _ = process_pdf(args.pdf_path)
        
        print(f"Sending to Bedrock ({MODEL_ID})...")
        print("Extraction successful.")
        
        with open(args.output, 'w') as f:
            json.dump(json_output, f, indent=2)
        
        print(f"Results saved to {args.output}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
