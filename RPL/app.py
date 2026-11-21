
import os
import json
import random
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from groq import Groq
from dotenv import load_dotenv

# ---------------- CONFIGURATION ----------------

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

if not API_KEY:
    raise ValueError("Groq API key missing. Check your .env file.")

client = Groq(api_key=API_KEY)

# DEMONSTRATION LIMITS ONLY.
# Replace these with limits approved for your actual facility.
CROP_LIMITS = {
    "Potato": {"min": 4.0, "max": 8.0},
    "Kinnow": {"min": 7.0, "max": 13.0}
}

# Electricity tariff periods (Indian local time)
PEAK_START = 18
PEAK_END = 22

# ---------------- SENSOR SIMULATION ----------------

def generate_sensor_data():

    random.seed(42)
    chambers = []

    for i in range(1, 41):

        if i <= 20:
            product = "Potato"
            temperature = round(5.5 + random.uniform(-1, 1), 1)
        else:
            product = "Kinnow"
            temperature = round(9.5 + random.uniform(-1, 1), 1)

        # Simulate abnormal temperature readings
        if i == 3:
            temperature = 10.0

        if i == 24:
            temperature = 15.0

        chambers.append({
            "id": i,
            "product": product,
            "temperature": temperature
        })

    return chambers


# ---------------- TEMPERATURE MONITORING AGENT ----------------

def monitor_chambers(chambers):

    results = []

    for chamber in chambers:

        product = chamber["product"]
        temp = chamber["temperature"]

        minimum = CROP_LIMITS[product]["min"]
        maximum = CROP_LIMITS[product]["max"]

        if temp < minimum - 2 or temp > maximum + 2:
            status = "CRITICAL"

        elif temp < minimum or temp > maximum:
            status = "WARNING"

        else:
            status = "NORMAL"

        results.append({
            **chamber,
            "minimum": minimum,
            "maximum": maximum,
            "status": status
        })

    return results


# ---------------- ELECTRICITY MONITORING ----------------

def electricity_status():

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    hour = now.hour

    if PEAK_START <= hour < PEAK_END:
        return "PEAK", now.strftime("%I:%M %p")

    return "OFF-PEAK", now.strftime("%I:%M %p")


def calculate_summary(results):

    normal = sum(
        1 for c in results if c["status"] == "NORMAL"
    )

    warning = sum(
        1 for c in results if c["status"] == "WARNING"
    )

    critical = sum(
        1 for c in results if c["status"] == "CRITICAL"
    )

    return {
        "total": len(results),
        "normal": normal,
        "warning": warning,
        "critical": critical
    }


# ---------------- GROQ AI AGENT ----------------

def get_ai_analysis(results, summary, tariff, current_time):

    prompt = f"""
    You are an AI advisor for a cold storage facility in Punjab.

    The facility contains 40 chambers storing potatoes and kinnow.

    CURRENT TIME: {current_time}
    ELECTRICITY PERIOD: {tariff}
    PEAK HOURS: 6 PM to 10 PM.

    MONITORING SUMMARY:
    {summary}

    CHAMBER READINGS:
    {results}

    YOUR TASK:

    1. Identify abnormal chambers.
    2. Explain which chambers need attention first.
    3. Recommend safe monitoring actions.
    4. Suggest ways to reduce electricity costs.
    5. Explain how peak electricity hours affect cooling plans.
    6. Never recommend compromising product safety.

    IMPORTANT:
    Python has already classified the readings.
    Do not change the classifications.
    Do not invent crop temperature limits.
    Do not assume that cooling can be switched off.
    Do not issue actual equipment control commands.

    Give a clear and structured report.
    """

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a cold storage energy and "
                    "temperature analysis assistant."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    return response.choices[0].message.content


# ---------------- DISPLAY DASHBOARD ----------------

def display_report(results, summary, tariff, current_time):

    print("\n" + "=" * 65)
    print("       SMART COLD STORAGE MANAGEMENT SYSTEM")
    print("=" * 65)

    print(f"Current Time: {current_time}")
    print(f"Electricity Period: {tariff}")

    print("\nCHAMBER MONITORING REPORT")
    print("-" * 65)

    print(
        f"{'ID':<6}{'PRODUCT':<12}"
        f"{'TEMP':<12}{'STATUS':<12}"
    )

    print("-" * 65)

    for c in results:

        print(
            f"{c['id']:<6}"
            f"{c['product']:<12}"
            f"{c['temperature']:<12}"
            f"{c['status']:<12}"
        )

    print("\nSYSTEM SUMMARY")
    print("-" * 65)

    print("Total Chambers :", summary["total"])
    print("Normal         :", summary["normal"])
    print("Warning        :", summary["warning"])
    print("Critical       :", summary["critical"])

    print("\nNOTE: All readings and limits are simulated.")


# ---------------- MAIN PROGRAM ----------------

# USER PROMPT AGENT

# Example inventory for demonstration
inventory = {
    i: {
        "product": "Potato" if i <= 20 else "Kinnow",
        "quantity": 0,
        "temperature": 5.5 if i <= 20 else 9.5,
        "setpoint": 5.5 if i <= 20 else 9.5
    }
    for i in range(1, 41)
}


def understand_prompt(user_prompt):

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": """
                You are a cold storage command assistant.

                Convert user requests into JSON.

                Supported actions:
                1. show_inventory
                2. count_product
                3. count_above_temperature
                4. set_temperature (absolute target temperature in Celsius)
                5. adjust_temperature (positive or negative change in Celsius)
                6. add_stock

                Return ONLY valid JSON with these fields:
                {
                    "action": "",
                    "product": null,
                    "quantity": null,
                    "temperature": null,
                    "adjustment": null,
                    "unit": "",
                    "chamber": null
                }

                For "increase temperature by 0.5 C", use action
                "adjust_temperature" and adjustment 0.5.
                For "decrease temperature by 0.5 C", use adjustment -0.5.
                For "set chamber 3 temperature to 6 C", use action
                "set_temperature", chamber 3, temperature 6.
                Extract a chamber number whenever the user gives one.
                Never invent missing values. Use null for unknown values.
                """
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        temperature=0
    )

    raw = (response.choices[0].message.content or "").strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    # Decode the first JSON object and ignore any extra text Groq may add.
    start = raw.find("{")
    if start == -1:
        raise ValueError(f"Groq did not return valid JSON: {raw}")
    try:
        command, _ = json.JSONDecoder().raw_decode(raw[start:])
    except json.JSONDecodeError as error:
        raise ValueError(f"Groq returned malformed JSON: {raw}") from error
    if not isinstance(command, dict):
        raise ValueError("Groq returned an invalid command.")
    return command


def execute_command(command):

    action = command.get("action")
    product = command.get("product")
    quantity = command.get("quantity")
    temperature = command.get("temperature")
    adjustment = command.get("adjustment")
    unit = command.get("unit")
    chamber_id = command.get("chamber")

    if isinstance(product, str) and product.strip().lower() in (
        "", "all", "both", "all products", "all chambers", "none", "null"
    ):
        product = None

    if product and product.lower() not in ("potato", "kinnow"):
        return f"Unknown product '{product}'. Please use Potato or Kinnow."

    if action == "show_inventory":
        matching = [
            {"chamber": i, **data}
            for i, data in inventory.items()
            if not product or data["product"].lower() == product.lower()
        ]
        return matching if matching else "No matching chambers found."

    elif action == "count_product":
        if not product:
            return "Please specify Potato or Kinnow."
        matching = [
            data for data in inventory.values()
            if data["product"].lower() == product.lower()
        ]
        return {
            "product": product,
            "chambers": len(matching),
            "quantity_kg": sum(x["quantity"] for x in matching)
        }

    elif action == "count_above_temperature":
        if temperature is None:
            return "Please specify a temperature."
        matching = [
            i for i, data in inventory.items()
            if data["temperature"] > float(temperature)
        ]
        return matching if matching else f"No chambers are above {temperature}°C."

    elif action in ("set_temperature", "adjust_temperature"):
        chamber_ids = command.get("chambers")
        if chamber_ids is None:
            chamber_ids = [chamber_id] if chamber_id is not None else []
        if not chamber_ids:
            return "Please specify a chamber number or range (1–40)."

        try:
            chamber_ids = sorted(set(int(x) for x in chamber_ids))
        except (TypeError, ValueError):
            return "Chamber numbers must be integers from 1 to 40."

        invalid = [x for x in chamber_ids if x not in inventory]
        if invalid:
            return f"Invalid chamber(s): {invalid}. Choose chambers from 1 to 40."

        messages = []
        for selected_id in chamber_ids:
            chamber_data = inventory[selected_id]
            crop = chamber_data["product"]
            limits = CROP_LIMITS[crop]

            try:
                if action == "adjust_temperature":
                    if adjustment is None:
                        return "Please specify how many °C to increase or decrease."
                    new_setpoint = float(chamber_data["setpoint"]) + float(adjustment)
                else:
                    if temperature is None:
                        return "Please specify the target temperature in °C."
                    new_setpoint = float(temperature)
            except (TypeError, ValueError):
                return "Temperature must be a valid number."

            new_setpoint = round(new_setpoint, 1)
            if not limits["min"] <= new_setpoint <= limits["max"]:
                messages.append(
                    f"Chamber {selected_id} ({crop}): REJECTED; "
                    f"allowed demonstration range {limits['min']}–{limits['max']}°C, "
                    f"requested {new_setpoint:.1f}°C."
                )
                continue

            old_setpoint = float(chamber_data["setpoint"])
            chamber_data["setpoint"] = new_setpoint
            messages.append(
                f"Chamber {selected_id} ({crop}): {old_setpoint:.1f}°C → "
                f"{new_setpoint:.1f}°C (simulated setpoint updated). "
                f"Sensor reading remains {chamber_data['temperature']:.1f}°C."
            )

        return "\n".join(messages)

    elif action == "add_stock":
        if not product or quantity is None:
            return "Please specify product and quantity."
        if unit not in ("kg", "tonnes"):
            return "Please specify quantity in kg or tonnes."
        quantity = float(quantity)
        if quantity <= 0:
            return "Quantity must be positive."
        if unit == "tonnes":
            quantity *= 1000
        available = [
            i for i, data in inventory.items()
            if data["product"].lower() == product.lower()
        ]
        if not available:
            return "No matching chambers are available."
        for chamber_id in available:
            inventory[chamber_id]["quantity"] += quantity / len(available)
        return f"Added {quantity:g} kg of {product} across {len(available)} chambers."

    return "Command not supported. Try: show inventory, count potatoes, count kinnow, or adjust chamber temperature."


def user_prompt_agent():

    print("\n===== COLD STORAGE AI CHAT =====")
    print("Examples:")
    print("  show inventory")
    print("  increase temperature by 0.5 C in chamber 3")
    print("  increase temperature by 1 C for chambers 1 to 5")
    print("  add temperature by 1 C for 1st and 2nd chamber")
    print("  set chamber 3 temperature to 6 C")
    print("Type 'exit' to finish.")

    pending_adjustment = None

    while True:
        try:
            prompt = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nChat closed safely.")
            break

        if not prompt:
            continue
        if prompt.lower() in ("exit", "quit", "stop"):
            break

        try:
            if pending_adjustment is not None:
                # Accept a single chamber, a range ("1 to 5"), or comma-separated IDs.
                range_match = re.search(r"(\d+)\s*(?:to|-)\s*(\d+)", prompt, re.IGNORECASE)
                if range_match:
                    first, last = map(int, range_match.groups())
                    if first > last:
                        first, last = last, first
                    command = dict(pending_adjustment)
                    command["chambers"] = list(range(first, last + 1))
                    pending_adjustment = None
                else:
                    nums = [int(x) for x in re.findall(r"\d+", prompt)]
                    if nums:
                        command = dict(pending_adjustment)
                        command["chambers"] = nums
                        pending_adjustment = None
                    else:
                        print("AI Agent: Enter a chamber number (1–40), a range (1 to 5), or 'cancel'.")
                        continue
            else:
                p = prompt.lower()

                if p == "cancel":
                    print("AI Agent: No change made.")
                    continue

                if any(word in p for word in ("inventory", "show chambers", "list chambers")):
                    if "potato" in p:
                        command = {"action": "show_inventory", "product": "Potato"}
                    elif "kinnow" in p:
                        command = {"action": "show_inventory", "product": "Kinnow"}
                    else:
                        command = {"action": "show_inventory", "product": None}
                else:
                    # Detect a chamber range or a single chamber in the same request.
                    range_match = re.search(
                        r"(?:chambers?\s*)?(\d+)\s*(?:to|-)\s*(\d+)", p, re.IGNORECASE
                    )
                    chamber_match = re.search(r"chamber\s*(\d+)", p)
                    # Understand ordinal wording such as "1st and 2nd chamber".
                    ordinal_ids = [int(x) for x in re.findall(r"\b(\d+)(?:st|nd|rd|th)\b", p)]
                    chamber_ids = sorted(set(ordinal_ids)) if ordinal_ids else None
                    chamber_id = int(chamber_match.group(1)) if chamber_match else None
                    if range_match:
                        first, last = map(int, range_match.groups())
                        if first > last:
                            first, last = last, first
                        chamber_ids = list(range(first, last + 1))
                    elif ordinal_ids:
                        chamber_ids = sorted(set(ordinal_ids))

                    amount_match = re.search(
                        r"by\s*(-?\d+(?:\.\d+)?)\s*(?:[°']?\s*c)?",
                        p, re.IGNORECASE
                    )
                    target_match = re.search(
                        r"(?:to|at)\s*(-?\d+(?:\.\d+)?)\s*(?:[°']?\s*c)?",
                        p, re.IGNORECASE
                    )

                    if any(word in p for word in ("increase", "raise", "add")) and amount_match:
                        command = {
                            "action": "adjust_temperature",
                            "adjustment": abs(float(amount_match.group(1))),
                            "chamber": chamber_id,
                            "chambers": chamber_ids
                        }
                    elif any(word in p for word in ("decrease", "lower", "reduce")) and amount_match:
                        command = {
                            "action": "adjust_temperature",
                            "adjustment": -abs(float(amount_match.group(1))),
                            "chamber": chamber_id,
                            "chambers": chamber_ids
                        }
                    elif ("set" in p or "change" in p) and "temperature" in p and target_match:
                        command = {
                            "action": "set_temperature",
                            "temperature": float(target_match.group(1)),
                            "chamber": chamber_id,
                            "chambers": chamber_ids
                        }
                    else:
                        command = understand_prompt(prompt)

                    if command.get("action") in ("set_temperature", "adjust_temperature"):
                        if command.get("chambers") is None and command.get("chamber") is None:
                            pending_adjustment = command
                            print("AI Agent: Which chamber(s)? Enter one number (e.g. 3) or a range (e.g. 1 to 5).")
                            continue

            result = execute_command(command)
            print("\nAI Agent:")
            if isinstance(result, list):
                if not result:
                    print("No matching records found.")
                else:
                    for item in result:
                        print(item)
            else:
                print(result)

        except Exception as error:
            pending_adjustment = None
            print("\nCould not process request:", error)
            print("Try: 'increase temperature by 1 C for chambers 1 to 5'.")


def main():

    print("\nStarting Cold Storage AI System...")

    current_time = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%d-%m-%Y %I:%M %p")

    tariff, _ = electricity_status()

    # Step 1: Collect readings
    chambers = generate_sensor_data()

    # Step 2: Monitor all chambers
    results = monitor_chambers(chambers)

    # Step 3: Calculate summary
    summary = calculate_summary(results)

    # Step 4: Display monitoring report
    display_report(
        results,
        summary,
        tariff,
        current_time
    )

    # Step 5: Get Groq AI recommendations
    print("\nConnecting to Groq AI Agent...")

    try:

        analysis = get_ai_analysis(
            results,
            summary,
            tariff,
            current_time
        )

        print("\n" + "=" * 65)
        print("             GROQ AI ANALYSIS")
        print("=" * 65)

        print(analysis)

    except Exception as error:

        print("\nAI ANALYSIS FAILED")
        print("Error:", error)

        print("Temperature monitoring is still available.")

    user_prompt_agent()
    print("\n" + "=" * 65)
    print("             SYSTEM COMPLETED")
    print("=" * 65)


if __name__ == "__main__":
    main()
