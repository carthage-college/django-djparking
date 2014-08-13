$(document).ready(function(){
    var LOADING_MESSAGE = 'Loading...';
    
    //Initialize autocomplete search box
    $('#search').autocomplete({
        source:'../ajax/search/' + $('select[name="academicYear"]').val() + '/',
        minLength:2,
        select:function(event, ui){
            $('#search').val(ui.item.value);
            $('input[name="searchID"]').val(ui.item.id);
            $('#mainSearchForm').submit();
        }
    });
    
    $('.iconSave').click(function(){
        $(this).parentsUntil('form').parent().submit();
    });
    $('.iconDelete').click(function() {
        $(this).parentsUntil('form').find('input[name="takeAction"]').val('delete');
        $(this).parentsUntil('form').parent().submit();
    });
    $('.iconAdd').click(function() { alert('Add a new vehicle record'); });
    
    //Initialize chosen drop downs
    $('.chosenDDL').chosen();
    $('.datepicker').datepicker();
    
    $('select[name="lot"]').each(function(){
        var thisVeh = $(this).data('veh');
        var selLot = 'select[name="lot"][data-veh="' + thisVeh + '"]',
            selPermit = 'select[name="sticker"][data-veh="' + thisVeh + '"]';

        $(selLot).change(function(){
            clearSelect(selPermit);
            loadSelect(selPermit, LOADING_MESSAGE, false);
            
            $.getJSON('../ajax/permits/' + $('select[name="academicYear"]').val() + '/' + $(selLot).val() + '/', function(){
                console.log('Beginning permit JSON request.');
            }).done(function(permitList){
                clearSelect(selPermit);
                loadSelect(selPermit, permitList, true);
            }).fail(function(jqxhr, textStatus, error){
                alert('Unable to retrieve the list of Permits. Please try again.');
                console.log('Request failed: ' + textStatus + ', ' + error);
            });
        });
    });
    
    //Loop through each Year select box
    $('select[name="carYear"]').each(function(){
        //Identify the veh_no value for the current row
        var thisVeh = $(this).data('veh');
        //Build the jQuery selector strings
        var selYear = 'select[name="carYear"][data-veh="' + thisVeh + '"]',
            selMake = 'select[name="carMake"][data-veh="' + thisVeh + '"]',
            selModel = 'select[name="carModel"][data-veh="' + thisVeh + '"]';

        //Initialize the "onchange" event for each Year select box
        $(selYear).change(function(){
            //Clear the values in the make and model dropdowns
            clearMultipleSelects(selMake + ',' + selModel);
            if($(selYear + ' :selected').not(selYear + ' :first')){
                //Put a loading placeholder in the make select box
                loadSelect(selMake, LOADING_MESSAGE, false);
                //Trigger the update event for the Chosen plugin select boxes.
                $(selMake + ',' + selModel).trigger('liszt:updated');

                $.getJSON('../ajax/makes/' + $(this).val() + '/', function(){
                    console.log('Beginning make JSON request.')
                }).done(function(makeList){
                    //Remove the loading placeholder
                    clearSelect(selMake);
                    //Update the list of makes with the results of the ajax call
                    loadSelect(selMake, makeList, true);
                    //Trigger the update event for the Chosen plugin
                    $(selMake).trigger('liszt:updated');
                }).fail(function(jqxhr, textStatus, error){
                    //If something goes wrong, let the user know and log the error to the console for debugging.
                    alert('Unable to retrieve the list of Makes. Please try again.');
                    console.log('Request failed: ' + textStatus + ', ' + error);
                });
            }
        });
    });

    //Loop through each Make select box
    $('select[name="carMake"]').each(function(){
        var thisVeh = $(this).data('veh');
        //Build the jQuery selector strings
        var selYear = 'select[name="carYear"][data-veh="' + thisVeh + '"]',
            selModel = 'select[name="carModel"][data-veh="' + thisVeh + '"]';

        //Initialize the "onchange" event for each Make select box
        $('select[name="carMake"][data-veh="' + thisVeh + '"]').change(function(){
            //Clear the values from the model dropdown
            clearSelect(selModel);
            //Put a loading placeholder in the model select box
            loadSelect(selModel, LOADING_MESSAGE, false);
            //Trigger the update event for the Chosen plugin
            $(selModel).trigger('liszt:updated');
            
            $.getJSON('../ajax/models/' + $(selYear).val() + '/' + $(this).val() + '/', function(){
                console.log('Beginning model JSON request.');
            }).done(function(modelList){
                //Remove the loading placeholder
                clearSelect(selModel);
                //Update the list of models with the results of the ajax call
                loadSelect(selModel, modelList, true);
                //Trigger the update for the Chosen plugin
                $(selModel).trigger('liszt:updated');
            }).fail(function(jqxhr, textStatus, error){
                //If something goes wrong, let the user know and log the error to the console for debugging.
                alert('Unable to retrieve the list of Models. Please try again.');
                console.log('Request failed: ' + textStatus + ', ' + error);
            });
        });
    });
});