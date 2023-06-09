$(function(){
    const loadingText = "<i class='fas fa-spinner fa-pulse'></i> Loading...";
    $(".single-submit-form").submit(function() {
        const button = $(this).find(":submit");
        button.html(loadingText);
        $(this).find(':submit').prop('disabled', true);
    });
});
