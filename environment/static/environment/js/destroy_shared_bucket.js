$(function(){
    const loadingText = "<i class='fas fa-spinner fa-pulse'></i> Destroying...";
    $(".shared-bucket-destroy").on("click", function() {
        $(this).html(loadingText);
    });
});
