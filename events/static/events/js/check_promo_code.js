function CheckPromoCode(event_id, default_price) {
  input = document.getElementById('id_promocode')
  var request = new XMLHttpRequest();
  var base_url = '/ajax/check_promo_code/?'
  var url = base_url + 'promocode=' + input.value + '&event_id=' + event_id
  request.open('GET', url, true);

  request.onload = function() {
    if (this.status >= 200 && this.status < 400) {
      var resp = JSON.parse(this.response);
      console.log(resp)
      amount_label = document.getElementById('id_amount')
      amount_send = document.getElementById('id_amount_send')
      if (resp['result']) {
        input.classList.remove('is-invalid');
        input.classList.add('is-valid');
        amount_label.innerText = resp['price'];
        amount_send.value = resp['price'];
      } else {
        input.classList.remove('is-valid');
        input.classList.add('is-invalid');
        amount_label.innerText = default_price;
        amount_send.value = default_price;
      }
    }
  };
  request.send();
};
