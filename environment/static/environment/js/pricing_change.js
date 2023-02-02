$(function(){
    var current_region = $("#id_region").val()
    $("#" + current_region).show()

    $("#id_region").on("change", function(){
        var current_region = $("#id_region").val()
        $("div.hidden").hide()
        $("#" + current_region).show()
    });
});
