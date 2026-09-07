def classify_temperature(row):
    temp = row["temperature_c"]
    min_c = row["temp_min_c"]
    max_c = row["temp_max_c"]

    if temp < min_c:
        return "TOO_COLD"
    if temp > max_c:
        return "TOO_HOT"
    return "OK"


if __name__ == "__main__":
    sample = {"temperature_c": 9.4, "temp_min_c": 2, "temp_max_c": 8}
    print(classify_temperature(sample))

