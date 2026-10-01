function confirm_action() {
    return confirm("Вы уверены?");
}

function copy_to_clipboard(element_id) {
    var copyText = document.getElementById(element_id);
    copyText.select();
    copyText.setSelectionRange(0, 99999); // For mobile devices
    navigator.clipboard.writeText(copyText.value);
}
