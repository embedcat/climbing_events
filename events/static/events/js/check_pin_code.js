function CheckPinCode(event_id, pin) {
  document.getElementById('alert-ok').style.display = 'none'
  document.getElementById('alert-error').style.display = 'none'
  var request = new XMLHttpRequest();
  var base_url = '/ajax/check_pin_code/?'
  var url = base_url + 'pin=' + pin + '&event_id=' + event_id
  request.open('GET', url, true);

  request.onload = function() {
    if (this.status >= 200 && this.status < 400) {
      var resp = JSON.parse(this.response);
      if (resp['result']) {
        document.getElementById('alert-ok').style.display = 'block'
        document.getElementById('alert-ok').innerHTML = 'Найден участник: ' + resp['participant']
        document.getElementById('enter-result-form').style.display = 'block'
        for ([key, value] of Object.entries(resp['accents'])) {
            document.getElementById("id_accents-" + key + "-accent_1").checked = value == "-";
            document.getElementById("id_accents-" + key + "-accent_2").checked = value == "F";
            document.getElementById("id_accents-" + key + "-accent_3").checked = value == "RP";
        }
      } else {
        document.getElementById('alert-error').innerHTML = resp['reason']
        document.getElementById('alert-error').style.display = 'block'
        document.getElementById('enter-result-form').style.display = 'none'
      }
    }
  };
    if (pin.length == 4) {
        request.send();
    }
};
