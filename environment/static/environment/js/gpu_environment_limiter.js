$(function(){
    var current_environment = $("input[value=rstudio]")
    var current_instance = $("#id_instance_type")
    current_instance.on("change", function(){
        if (current_instance.val() == "a2-highgpu-1g") {
            current_environment.parent().parent().hide()
        } else {
            current_environment.parent().parent().show()
        }
    });
});
