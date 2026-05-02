def calculate_trust_score(row):
    score = 0

    # Delivery
    if row['on_time_delivery'] >= 80:
        score += 30
    else:
        score += 10

    # Quality
    if row['quality_rating'] >= 4:
        score += 30
    else:
        score += 10

    # Defect
    if row['defect_rate'] < 5:
        score += 20
    else:
        score += 5

    # Response
    if row['response_time'] < 24:
        score += 20
    else:
        score += 5

    return score


def get_trust_level(score):
    if score >= 80:
        return "High Trust"
    elif score >= 50:
        return "Medium Trust"
    else:
        return "Low Trust"