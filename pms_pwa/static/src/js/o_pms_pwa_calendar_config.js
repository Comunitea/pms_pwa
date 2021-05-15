odoo.define("pms_pwa.calendar_config", function (require) {
    "use strict";
    require("web.dom_ready");
    var ajax = require("web.ajax");
    var core = require("web.core");
    var publicWidget = require("web.public.widget");
    var csrf_token = core.csrf_token;

    publicWidget.registry.CalendarConfigSendWidget = publicWidget.Widget.extend({
        selector: "#buttom_save",
        events: {
            "click #save": "_onClickSendCalendarData",
        },

        _onClickSendCalendarData: function (event) {
            event.preventDefault();

            var room_type = {};
            $("#calendar_conf_table_line input").each(function (index) {
                var input = $(this);
                if (input.data("edit") === true) {
                    var input_array = {};
                    // Value['pricelist_id'].push(input.data('pricelist'));
                    input_array[input.attr("name")] = input.val();
                    var price = input.data("pricelist");
                    var room = input.data("room");
                    var date = input.data("date");
                    var input_name = input.attr("name");
                    var current_datetime = new Date(date);
                    const formatted_date =
                        current_datetime.getDate() +
                        "-" +
                        (current_datetime.getMonth() + 1) +
                        "-" +
                        current_datetime.getFullYear();
                    console.log(formatted_date);
                    // Console.log("price ", price);
                    room_type[room] = {};
                    room_type[room].pricelist_id = {};
                    room_type[room].pricelist_id[price] = {};
                    room_type[room].pricelist_id[price].date = {};
                    // Value['room_type'][room]['pricelist_id'][price]['date'].push(formatted_date);
                    room_type[room].pricelist_id[price].date[formatted_date] = [];
                    room_type[room].pricelist_id[price].date[formatted_date].push(
                        input_array
                    );
                }
            });
            console.log(room_type);
            ajax.jsonRpc("/calendar/config/save", "call", {
                room_type,
            }).then(function (data) {
                console.log(data);
            });
        },
    });

    $("#calendar_config_table").on("change", "input[type='text']", function () {
        this.style.backgroundColor = "yellow";
        var element = document.getElementById("save");
        $(this).data("edit", true);
        element.classList.remove("d-none");
    });
});
