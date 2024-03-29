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
        if (resp['accents']) {
          for ([key, value] of Object.entries(resp['accents'])) {
              document.getElementById("id_accents-" + key + "-top_1").checked = value['top'] == 0;
              document.getElementById("id_accents-" + key + "-top_2").checked = value['top'] == 1;
              document.getElementById("id_accents-" + key + "-top_3").checked = value['top'] == 2;
          }
        }
        if (resp['french_accents']) {
          for ([key, value] of Object.entries(resp['french_accents'])) {
              $("#" + "id_accents-" + key + "-top").val(value['top'])
              $("#" + "id_accents-" + key + "-zone").val(value['zone'])
          }
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
