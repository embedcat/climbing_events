var isMacLike = !!navigator.platform.match(/(Mac|iPhone|iPod|iPad)/i),
    platformClassName = isMacLike ? "platform-mac" : "";
function onReady() {
    var a = document.querySelector(".main-navigation");
    document.querySelector(".js-extend-main-navigation").addEventListener(
        "click",
        function (e) {
            e.preventDefault(), a.classList.toggle("extended");
        },
        !1
    );
    var e = document.querySelector && document.querySelector("html");
    e && (e.className += " " + platformClassName);
}
document.addEventListener("DOMContentLoaded", onReady);

function confirm_action() {
    return confirm("Вы уверены?");
}

function copy_to_clipboard(element_id) {
    var copyText = document.getElementById(element_id);
    copyText.select();
    copyText.setSelectionRange(0, 99999); // For mobile devices
    navigator.clipboard.writeText(copyText.value);
}

function page_reload() {
    setTimeout(() => {
        document.location.reload();
      }, 10000);
}