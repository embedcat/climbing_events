import requests
from yoomoney import Quickpay


def quickpay():
    base_url = "https://yoomoney.ru/quickpay/confirm.xml?"

    payload = {
        "receiver": "410019014512803",
        "quickpay-form": "shop",
        "paymentType": "PC",
        "sum": "15",
        "label": "abcabc123",
        "need-email": "true",
    }

    for value in payload:
        base_url += str(value).replace("_", "-") + "=" + str(payload[value])
        base_url += "&"

    base_url = base_url[:-1].replace(" ", "%20")

    response = requests.request("POST", base_url)

    redirected_url = response.url
    return redirected_url


#
# quickpay = Quickpay(
#             receiver="410013922384058",
#             quickpay_form="small",
#             label="Sponsor this project",
#             paymentType="SB",
#             sum=15,
#             targets=""
#             )
# print(quickpay.base_url)
# print(quickpay.redirected_url)

if __name__ == "__main__":
    url = quickpay()
    print(url)
