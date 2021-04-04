function CheckPinCode(event, event_id, pin) {
  document.getElementById('alert-ok').style.display = 'none'
  document.getElementById('alert-error').style.display = 'none'
  var request = new XMLHttpRequest();
  var base_url = '/ajax/check_pin_code/?'
  var url = base_url + 'pin=' + pin + '&event_id=' + event_id
  request.open('GET', url, true);

  request.onload = function() {
    if (this.status >= 200 && this.status < 400) {
      var resp = JSON.parse(this.response);
      find_result = resp['Find']
      if (find_result) {
        document.getElementById('alert-ok').style.display = 'block'
        document.getElementById('alert-ok').innerHTML = 'Найден участник: ' + resp['participant']
        document.getElementById('enter-result-form').style.display = 'block'
      } else {
          document.getElementById('alert-error').style.display = 'block'

      }

    }
  };
    if (pin.length == 4) {
        request.send();
    }
};

function foo(value) {
    console.log(value)
};