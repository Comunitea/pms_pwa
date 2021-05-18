# Part of Odoo. See LICENSE file for full copyright and licensing details.

# -*- coding: utf-8 -*-

import datetime
import json
import logging
import pprint
from calendar import monthrange
from datetime import timedelta

from odoo import _, fields, http
from odoo.exceptions import MissingError
from odoo.http import request
from odoo.tools.misc import format_date, formatLang, get_lang

from odoo.addons.web.controllers.main import Home

from . import room_types, rooms

pp = pprint.PrettyPrinter(indent=4)

_logger = logging.getLogger(__name__)


class PWAHome(Home):
    @http.route()
    def index(self, *args, **kw):
        if request.session.uid and request.env["res.users"].sudo().browse(
            request.session.uid
        ).has_group("pms_pwa.group_pms_property_user"):
            return http.local_redirect("/", query=request.params, keep_hash=True)
        return super(Home, self).index(*args, **kw)

    def _login_redirect(self, uid, redirect=None):
        if not redirect and request.env["res.users"].sudo().browse(uid).has_group(
            "pms_pwa.group_pms_property_user"
        ):
            return "/"
        return super(PWAHome, self)._login_redirect(uid, redirect=redirect)


# Frontend controllers to test
class TestFrontEnd(http.Controller):
    def _get_reservation_types(self):
        return [
            {"id": "out", "name": "Out of service"},
            {"id": "normal", "name": "Normal"},
            {"id": "staff", "name": "Staff"},
        ]

    def _get_allowed_payments_journals(self):
        """
        @return: Return dict with journals
         [
          {"id": id, "name": name},
          {"id": id, "name": name},
          ...
          {"id": id, "name": name},
         ]
        """
        payment_methods = (
            request.env["account.journal"]
            .sudo()
            .search([("type", "in", ["bank", "cash"])])
        )
        allowed_journals = []
        for journal in payment_methods:
            allowed_journals.append({"id": journal.id, "name": journal.name})
        return allowed_journals

    def _get_allowed_channel_type_ids(self):
        channel_types = request.env["pms.sale.channel"].search([])
        allowed_channel_types = []
        for channel in channel_types:
            allowed_channel_types.append({"id": channel.id, "name": channel.name})
        return allowed_channel_types

    def _get_allowed_agency_ids(self):
        agencies = request.env["res.partner"].search([("is_agency", "=", True)])
        allowed_agencies = []
        for agency in agencies:
            allowed_agencies.append({"id": agency.id, "name": agency.name})
        return allowed_agencies

    @http.route(
        ["/reservation/list", "/reservation/list/page/<int:page>"],
        type="http",
        auth="user",
        methods=["GET", "POST"],
        website=True,
    )
    def reservation_list(self, page=0, search=False, sortby=None, **post):
        if post and "original_search" in post:
            if not search:
                search = post["original_search"]
            post.pop("original_search")
        # REVIEW: magic number
        paginate_by = 15

        # TODO: ORDER STUFF's
        # searchbar_sortings = {
        #     "priority":
        #         {
        #             "label": _("Priority"),
        #             "order": "priority"
        #         },
        #     }
        # if not sortby:
        #     sortby = "priority"
        # sort_folio = searchbar_sortings[sortby]["order"]
        # sortby = 'priority'
        # / ORDER STUFF's

        pager = request.website.pager(
            url="/reservation/list",
            total=request.env["pms.folio"].search_count_folios_pwa(search, **post),
            page=page,
            step=paginate_by,
            url_args=post,
        )

        values = {
            "folios": request.env["pms.folio"].search_folios_pwa(
                search=search,
                # order=sort_folio,  #TODO: REVIEW SORTING
                limit=paginate_by,
                offset=pager["offset"],
                **post
            ),
            "page_name": "Reservations",
            "pager": pager,
            "search": search if search else None,
            "default_url": "",
            "post": post if post else None,
            # "searchbar_sortings": searchbar_sortings, #TODO: REVIEW SORTING
            "sortby": sortby,
        }

        return http.request.render("pms_pwa.roomdoo_reservation_list", values)

    @http.route(
        "/reservation/<int:reservation_id>/assign",
        type="json",
        auth="public",
        csrf=False,
        website=True,
    )
    def reservation_assign(self, reservation_id=None, **kw):
        if reservation_id:
            reservation = (
                request.env["pms.reservation"]
                .sudo()
                .search([("id", "=", int(reservation_id))])
            )
            reservation.action_assign()
            return json.dumps(
                {"result": True, "message": _("Operation completed successfully.")}
            )
        return json.dumps({"result": False, "message": _("Reservation not found")})

    @http.route(
        "/reservation/<int:reservation_id>/cancel",
        type="json",
        auth="public",
        csrf=False,
        website=True,
    )
    def reservation_cancel(self, reservation_id=None, **kw):
        if reservation_id:
            reservation = (
                request.env["pms.reservation"]
                .sudo()
                .search([("id", "=", int(reservation_id))])
            )
            try:
                reservation.action_cancel()
            except Exception as e:
                return json.dumps({"result": False, "message": str(e)})
            return json.dumps(
                {"result": True, "message": _("Operation completed successfully.")}
            )
        return json.dumps({"result": False, "message": _("Reservation not found")})

    @http.route(
        "/reservation/<int:reservation_id>/checkout",
        type="json",
        auth="public",
        csrf=False,
        website=True,
    )
    def reservation_checkout(self, reservation_id=None, **kw):
        if reservation_id:
            reservation = (
                request.env["pms.reservation"]
                .sudo()
                .search([("id", "=", int(reservation_id))])
            )

            try:
                reservation.action_reservation_checkout()
            except Exception as e:
                return json.dumps({"result": False, "message": str(e)})
            return json.dumps(
                {"result": True, "message": _("Operation completed successfully.")}
            )
        return json.dumps({"result": False, "message": _("Reservation not found")})

    @http.route(
        "/reservation/<int:reservation_id>/checkin",
        type="json",
        auth="public",
        csrf=False,
        website=True,
    )
    def reservation_checkin(self, reservation_id=None, **kw):
        if reservation_id:
            reservation = (
                request.env["pms.reservation"]
                .sudo()
                .search([("id", "=", int(reservation_id))])
            )
            try:
                params = http.request.jsonrequest.get("params")
                reservation.pwa_action_checkin(params["guests_list"], reservation_id)
            except Exception as e:
                return json.dumps({"result": False, "message": str(e)})
            return json.dumps(
                {"result": True, "message": _("Operation completed successfully.")}
            )
        return json.dumps({"result": False, "message": _("Reservation not found")})

    @http.route(
        "/reservation/<int:reservation_id>/payment",
        type="json",
        auth="public",
        csrf=False,
        website=True,
    )
    def reservation_payment(self, reservation_id=None, **kw):
        if reservation_id:
            reservation = (
                request.env["pms.reservation"]
                .sudo()
                .search([("id", "=", int(reservation_id))])
            )
            if reservation:
                payload = http.request.jsonrequest.get("params")
                payment_method = int(payload["payment_method"])
                payment_amount = float(payload["amount"])
                if "partner_id" in payload:
                    payment_partner_id = int(payload["partner_id"])
                else:
                    payment_partner_id = reservation.partner_id.id
                try:
                    account_journals = (
                        reservation.folio_id.pms_property_id._get_payment_methods()
                    )
                    journal = account_journals.browse(payment_method)
                    partner_id = request.env["res.partner"].browse(
                        int(payment_partner_id)
                    )
                    if reservation.folio_payment_state != "paid":
                        reservation.folio_id.do_payment(
                            journal,
                            journal.suspense_account_id,
                            request.env.user,
                            payment_amount,
                            reservation.folio_id,
                            partner=partner_id
                            if partner_id
                            else reservation.partner_id,
                            date=fields.date.today(),
                        )
                    else:
                        return json.dumps(
                            {"result": False, "message": _("Reservation already paid.")}
                        )
                except Exception as e:
                    return json.dumps({"result": False, "message": str(e)})
                return json.dumps(
                    {"result": True, "message": _("Operation completed successfully.")}
                )
            return json.dumps({"result": False, "message": _("Reservation not found")})

    @http.route(
        "/reservation/<int:reservation_id>/invoice",
        type="json",
        auth="public",
        csrf=False,
        website=True,
    )
    def reservation_invoice(self, reservation_id=None, **kw):
        if reservation_id:
            reservation = (
                request.env["pms.reservation"]
                .sudo()
                .search([("id", "=", int(reservation_id))])
            )

            if reservation:
                payload = http.request.jsonrequest["params"]["data"]
                invoice_lines = payload[0]["lines_to_invoice"]
                partner_invoice_id = payload[0]["partner_to_invoice"]
                partner_invoice_values = payload[0]["partner_values"][0]
                try:
                    if partner_invoice_id:
                        partner_invoice_id = (
                            request.env["res.partner"]
                            .sudo()
                            .search([("id", "=", int(partner_invoice_id))])
                        )
                    else:
                        partner_invoice_id = request.env["res.partner"].create(
                            partner_invoice_values
                        )
                    lines_to_invoice = dict()
                    for value in invoice_lines:
                        lines_to_invoice[value[0]["id"]] = value[0]["qty"]
                    reservation.folio_id._create_invoices(
                        lines_to_invoice=lines_to_invoice,
                        partner_invoice_id=partner_invoice_id,
                    )
                except Exception as e:
                    return json.dumps({"result": False, "message": str(e)})
                return json.dumps(
                    {
                        "result": True,
                        "message": _("Operation completed successfully."),
                        "invoices": reservation.folio_id.move_ids.ids,
                    }
                )
            return json.dumps({"result": False, "message": _("Reservation not found")})

    @http.route(
        "/",
        type="http",
        auth="user",
        methods=["GET", "POST"],
        website=True,
    )
    def dashboard(self, **post):
        values = {}

        def _get_user_activities(uid=False):
            activities = []
            if uid:
                activities = [
                    activity
                    for activity in request.env["mail.activity"].search(
                        [("user_id", "in", [uid])]
                    )
                ]
            return activities

        values.update(
            {
                "tasks": _get_user_activities(
                    request.session.uid if request.session.uid else False
                ),
                "arrivals": {
                    "today": {
                        "date": "14/10/2020",
                        "to_arrive": 10,
                        "to_check_in": 2,
                    },
                    "tomorrow": {
                        "date": "15/10/2020",
                        "to_arrive": 8,
                    },
                },
                "departures": {
                    "today": {
                        "date": "14/10/2020",
                        "to_leave": 10,
                        "to_check_out": 2,
                    },
                    "tomorrow": {
                        "date": "15/10/2020",
                        "to_leave": 8,
                    },
                },
                "rooms": {
                    "date": "14/10/2020",
                    "available": 10,
                    "out_of_service": 2,
                    "taken": 8,
                    "ready": 1,
                    "dirty": 1,
                    "cleaning": 2,
                },
                "clocking_in": [
                    {"name": "Juan Manuel Díaz", "date": "15/10/2020 10:19:25"},
                    {"name": "Paula Sánchez", "date": "15/10/2020 10:54:25"},
                ],
                "deliveries": [
                    {"name": "Envío fichero a la policía", "date": "15/10/2020"},
                    {"name": "Envío facturas al gestor", "date": "15/10/2020"},
                ],
                "history": [
                    {
                        "date": "15/10/2020",
                        "hour": "10:14:58",
                        "name": "Nueva reserva",
                        "description": "Lorem ipsum dolor sit amet, consectetur"
                        " adipiscing elit. Nulla sit amet enim sit amet ex laoreet dictum.",
                    },
                    {
                        "date": "15/10/2020 10:54:25",
                        "hour": "10:14:58",
                        "name": "Nueva reserva",
                        "description": "Lorem ipsum dolor sit amet, consectetur"
                        " adipiscing elit. Nulla sit amet enim sit amet ex laoreet dictum.",
                    },
                ],
                "evolutions": [
                    {
                        "name": "Billing",
                        "selector": "billing",
                        "labels": "5 oct,6 oct,7 oct,8 oct,9 oct",
                        "label_1": "2019",
                        "data_1": "12,24,13,3,54",
                        "backgroundColor_1": "#E5F8FC",
                        "borderColor_1": "#00B5E2",
                        "label_2": "2020",
                        "data_2": "15,19,25,69,12",
                        "backgroundColor_2": "#CEF2E8",
                        "borderColor_2": "#00BA39",
                    },
                    {
                        "name": "Revenue",
                        "selector": "revenue",
                        "labels": "19 nov,20 nov,21 nov,22 nov,23 nov",
                        "label_1": "2019",
                        "data_1": "200,210,130,36,540",
                        "backgroundColor_1": "#E5F8FC",
                        "borderColor_1": "#00B5E2",
                        "label_2": "2020",
                        "data_2": "150,190,250,690,120",
                        "backgroundColor_2": "#CEF2E8",
                        "borderColor_2": "#00BA39",
                    },
                    {
                        "name": "Ocupation",
                        "selector": "ocupation",
                        "labels": "5 sept,6 sept,7 sept",
                        "label_1": "2019",
                        "data_1": "315,850,130",
                        "backgroundColor_1": "#E5F8FC",
                        "borderColor_1": "#00B5E2",
                        "label_2": "2020",
                        "data_2": "150,650,250",
                        "backgroundColor_2": "#CEF2E8",
                        "borderColor_2": "#00BA39",
                    },
                ],
                "kpis": [
                    {
                        "name": "Ocupation",
                        "labels": "Arrivals,Departures,No show",
                        "label": "",
                        "data": "12,24,18",
                        "backgroundColor": "#FF5733,#B5BFBD,#00B5E2",
                        "borderColor": "#FF5733,#B5BFBD,#00B5E2",
                        "ratio": 3.99,
                    },
                    {
                        "name": "Reservations by channel",
                        "labels": "Phone,Booking,Other",
                        "label": "",
                        "data": "14,7,5",
                        "backgroundColor": "#FF5733,#B5BFBD,#00B5E2",
                        "borderColor": "#FF5733,#B5BFBD,#00B5E2",
                        "ratio": 4.21,
                    },
                    {
                        "name": "Income by channel",
                        "labels": "Phone,Booking,Other",
                        "label": "",
                        "data": "1400,700,500",
                        "backgroundColor": "#FF5733,#B5BFBD,#00B5E2",
                        "borderColor": "#FF5733,#B5BFBD,#00B5E2",
                        "ratio": 4.66,
                    },
                    {
                        "name": "Cleaning score",
                        "labels": "Good,Acceptable,Bad",
                        "label": "",
                        "data": "54,24,14",
                        "backgroundColor": "#FF5733,#B5BFBD,#00B5E2",
                        "borderColor": "#FF5733,#B5BFBD,#00B5E2",
                        "ratio": 3.16,
                    },
                    {
                        "name": "Attention score",
                        "labels": "Good,Acceptable,Bad",
                        "label": "",
                        "data": "55,20,11",
                        "backgroundColor": "#FF5733,#B5BFBD,#00B5E2",
                        "borderColor": "#FF5733,#B5BFBD,#00B5E2",
                        "ratio": 4.05,
                    },
                    {
                        "name": "General score",
                        "labels": "Good,Acceptable,Bad",
                        "label": "",
                        "data": "64,34,4",
                        "backgroundColor": "#FF5733,#B5BFBD,#00B5E2",
                        "borderColor": "#FF5733,#B5BFBD,#00B5E2",
                        "ratio": 4.25,
                    },
                ],
                "compare_options": [
                    {
                        "id": 1,
                        "value": "Previous year",
                    },
                    {
                        "id": 2,
                        "value": "Two years ago",
                    },
                ],
            }
        )

        return http.request.render("pms_pwa.roomdoo_dashboard_page", values)

    @http.route(
        "/reservation/<int:reservation_id>",
        type="http",
        auth="user",
        methods=["GET", "POST"],
        website=True,
    )
    def reservation_detail(self, reservation_id, **post):
        reservation = request.env["pms.reservation"].browse([reservation_id])
        if not reservation:
            raise MissingError(_("This document does not exist."))
        values = {
            "page_name": "Reservation",
            "reservation": reservation,
        }
        if post and "message" in post:
            try:
                reservation.message_post(
                    subject=_("PWA Message"),
                    body=post["message"],
                    message_type="comment",
                )
            except Exception as e:
                _logger.critical(e)
        return http.request.render("pms_pwa.roomdoo_reservation_detail", values)

    @http.route(
        "/reservation/reservation_lines",
        type="json",
        auth="public",
        csrf=False,
        methods=["POST"],
        website=True,
    )
    def reservation_lines_json(
        self, reservation_ids=False, invoice_lines=False, folio_id=False, **kw
    ):
        if folio_id and reservation_ids:
            folio = request.env["pms.folio"].sudo().search([("id", "=", int(folio_id))])
            if not folio:
                raise MissingError(_("This document does not exist."))
            if reservation_ids:
                # TODO resisar si se puede hacer de otra forma.
                reservation_lines = folio.sale_line_ids.filtered(
                    lambda x: x.reservation_id.id in reservation_ids and x.display_type == False
                )
                reservation_show_lines = [
                    {
                        "id": x.id,
                        "name": x.product_id.name,
                        "qty_to_invoice": x.qty_to_invoice,
                        "qty_invoiced": x.qty_invoiced,
                        "price_total": x.price_total,
                        "price_subtotal": x.price_subtotal,
                        "product_uom_qty": x.product_uom_qty,
                    }
                    for x in reservation_lines
                ]
                if invoice_lines:
                    reservation_show_lines = [
                        x for x in reservation_show_lines if x["id"] in invoice_lines
                    ]
                total_amount = sum(
                    [float(x["price_total"]) for x in reservation_show_lines]
                )
                data = {
                    "reservation_lines": reservation_show_lines,
                    "total_amount": total_amount,
                }
                return data
        print("PEPEPE")
        return json.dumps({"result": False, "message": _("Reservation not found")})

    @http.route(
        ["/reservation/json_data"],
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def reservation_detail_json(self, reservation_id=None, **kw):
        reservation = False
        if reservation_id:
            reservation = (
                request.env["pms.reservation"]
                .sudo()
                .search([("id", "=", int(reservation_id))])
            )
        if not reservation:
            raise MissingError(_("This document does not exist."))

        buttons = json.loads(reservation.pwa_action_buttons)
        keys = buttons.keys()
        keysList = [key for key in keys]

        primary_button = ""
        secondary_buttons = ""

        counter = 0
        for _key in keysList:
            if counter == 0 or keysList[counter] == "Ver Detalle":
                if buttons[keysList[counter]]:
                    primary_button = (
                        "<button url='"
                        + buttons[keysList[counter]]
                        + "' class='btn o_pms_pwa_default_button_name"
                        + " o_pms_pwa_abutton o_pms_pwa_button_"
                        + str(keysList[counter].lower())
                        + "' type='button'>"
                        + keysList[counter]
                        + "</button>"
                    )
                else:
                    primary_button = (
                        "<button"
                        + " class='disabled btn o_pms_pwa_default_button_name"
                        + " o_pms_pwa_abutton o_pms_pwa_button_"
                        + str(keysList[counter].lower())
                        + "' type='button'>"
                        + keysList[counter]
                        + "</button>"
                    )
            else:
                if buttons[keysList[counter]]:
                    secondary_buttons += (
                        "<button url='"
                        + buttons[keysList[counter]]
                        + "' class='dropdown-item  o_pms_pwa_abutton o_pms_pwa_button_"
                        + str(keysList[counter].lower())
                        + "' type='button'>"
                        + keysList[counter]
                        + "</button>"
                    )
                else:
                    secondary_buttons += (
                        "<button class='disabled dropdown-item"
                        + " o_pms_pwa_abutton o_pms_pwa_button_"
                        + str(keysList[counter].lower())
                        + "' type='button'>"
                        + keysList[counter]
                        + "</button>"
                    )
            counter += 1

        reservation_values = {
            "id": reservation.id,
            "name": reservation.name,
            "partner_id": {
                "id": reservation.partner_id.id,
                "name": reservation.partner_id.name,
                "mobile": reservation.partner_id.mobile or reservation.partner_id.phone,
            },
            "unread_msg": 2,
            "messages": ["Lorem ipsum", "Unread short message"],
            "room_type_id": {
                "id": reservation.room_type_id.id,
                "name": reservation.room_type_id.name,
            },
            "preferred_room_id": {
                "id": reservation.preferred_room_id.id
                if reservation.preferred_room_id
                else False,
                "name": reservation.preferred_room_id.name
                if reservation.preferred_room_id
                else reservation.rooms,
            },
            "channel_type_id": {
                "id": reservation.channel_type_id.id
                if reservation.channel_type_id
                else False,
                "name": reservation.channel_type_id.name
                if reservation.channel_type_id
                else False,
            },
            "agency_id": {
                "id": reservation.agency_id.id if reservation.agency_id else False,
                "name": reservation.agency_id.name if reservation.agency_id else False,
            },
            "nights": reservation.nights,
            "checkin": reservation.checkin.strftime(get_lang(request.env).date_format),
            "arrival_hour": reservation.arrival_hour,
            "checkout": reservation.checkout.strftime(
                get_lang(request.env).date_format
            ),
            "departure_hour": reservation.departure_hour,
            "folio_id": {
                "id": reservation.folio_id.id,
                "amount_total": reservation.folio_id.amount_total,
                "outstanding_vat": reservation.folio_pending_amount,
            },
            "state": reservation.state,
            "credit_card_details": reservation.credit_card_details,
            "price_total": reservation.price_total,
            "price_tax": reservation.price_tax,
            "folio_pending_amount": reservation.folio_pending_amount,
            "folio_internal_comment": reservation.folio_internal_comment,
            "payment_methods": self._get_allowed_payments_journals(),
            "reservation_types": self._get_reservation_types(),
            "checkins_ratio": reservation.checkins_ratio,
            "ratio_checkin_data": reservation.ratio_checkin_data,
            "adults": reservation.adults,
            "checkin_partner_ids": reservation._get_checkin_partner_ids(),
            "pms_property_id": reservation.pms_property_id.id,
            "service_ids": reservation._get_service_ids(),
            "reservation_line_ids": reservation._get_reservation_line_ids(),
            "allowed_board_service_room_ids": reservation._get_allowed_board_service_room_ids(),
            "board_service_room_id": {
                "id": reservation.board_service_room_id.id,
                "name": reservation.board_service_room_id.display_name,
            },
            "allowed_service_ids": reservation._get_allowed_service_ids(),
            "primary_button": primary_button,
            "secondary_buttons": secondary_buttons,
            "pricelist_id": reservation.pricelist_id.id,
            "allowed_pricelists": reservation._get_allowed_pricelists(),
            "allowed_segmentations": reservation._get_allowed_segmentations(),
            "allowed_channel_type_ids": self._get_allowed_channel_type_ids(),
            "allowed_agency_ids": self._get_allowed_agency_ids(),
        }

        pp.pprint(reservation_values)
        return reservation_values

    @http.route(
        ["/reservation/<int:reservation_id>/onchange_data"],
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
    )
    # flake8: noqa: C901
    def reservation_onchange_data(self, reservation_id=None, **kw):
        old_reservation_type = None
        reservation = False
        params = http.request.jsonrequest.get("params")
        _logger.info(params)
        # TEMP FIX
        ##############################################################################
        if (
            "checkin" in params
            and "checkout" in params
            and datetime.datetime.strptime(
                params["checkin"].strip(), get_lang(request.env).date_format
            )
            >= datetime.datetime.strptime(
                params["checkout"].strip(), get_lang(request.env).date_format
            )
        ):
            return
        ##############################################################################
        if reservation_id:
            reservation = (
                request.env["pms.reservation"]
                .sudo()
                .search([("id", "=", int(reservation_id))])
            )
        if not reservation:
            raise MissingError(_("This reservation does not exist."))
        if reservation:
            try:
                params = http.request.jsonrequest.get("params")
                reservation_line_cmds = []
                reservation_values = {}
                for param in params.keys():
                    # DEL SERVICE
                    if param == "del_service":
                        reservation_values["service_ids"] = [
                            (2, int(params["del_service"]))
                        ]

                    # ADD SERVICE
                    if param == "add_service":
                        reservation_values["service_ids"] = [
                            (0, 0, {"product_id": int(params["add_service"])})
                        ]
                    # ADULTS
                    if (
                        param == "adults"
                        and int(params["adults"]) != reservation.adults
                    ):
                        reservation_values["adults"] = int(params["adults"])

                    # ROOM TYPE
                    elif (
                        param == "room_type_id"
                        and int(params["room_type_id"]) != reservation.room_type_id
                    ):
                        reservation_values["room_type_id"] = request.env[
                            "pms.room.type"
                        ].browse(int(params["room_type_id"]))


                    # PREFERRED ROOM ID
                    elif (
                        param == "preferred_room_id"
                        and int(params["preferred_room_id"])
                        != reservation.preferred_room_id
                    ):
                        reservation_values["preferred_room_id"] = request.env[
                            "pms.room"
                        ].browse(int(params["preferred_room_id"]))

                    # CHECKIN & CHECKOUT TODO process both as an unit
                    elif (
                        param == "checkin"
                        and datetime.datetime.strptime(
                            params["checkin"].strip(), get_lang(request.env).date_format
                        ).date()
                        != reservation.checkin
                    ):
                        # TODO:  Delete Strip
                        reservation_values["checkin"] = datetime.datetime.strptime(
                            params["checkin"].strip(), get_lang(request.env).date_format
                        )
                    elif (
                        param == "checkout"
                        and datetime.datetime.strptime(
                            params["checkout"].strip(),
                            get_lang(request.env).date_format,
                        ).date()
                        != reservation.checkout
                    ):
                        reservation_values["checkout"] = datetime.datetime.strptime(
                            params["checkout"], get_lang(request.env).date_format
                        )

                    # BOARD_SERVICE
                    elif (
                        param == "board_service_room_id"
                        and int(params["board_service_room_id"])
                        != reservation.board_service_room_id
                    ):
                        reservation_values["board_service_room_id"] = request.env[
                            "pms.room"
                        ].browse(int(params["board_service_room_id"]))

                    # SEGMENTATION
                    # TODO

                    # RESERVATION_LINE
                    elif param == "reservation_line_ids":
                        reservation_values.update(
                            self.parse_params_record(
                                origin_values={
                                    "reservation_line_ids": params[
                                        "reservation_line_ids"
                                    ]
                                },
                                model=request.env["pms.reservation"],
                            )
                        )

                    # ELIF CHANGE SERVICES LINES
                    elif param == "service_ids":
                        reservation_values.update(
                            self.parse_params_record(
                                origin_values={"service_ids": params["service_ids"]},
                                model=request.env["pms.reservation"],
                            ),
                        )
                    elif (
                        param == "reservation_type"
                        and params["reservation_type"] != reservation.reservation_type
                    ):
                        reservation_values.folio_id.reservation_type = params[param]

                if "add_service" in params:
                    del params["add_service"]
                if "del_service" in params:
                    del params["del_service"]
                if "reservation_type" in params:
                    del params["reservation_type"]
                if "board_service" in params:
                    del params["board_service"]
                if "price_total" in params:
                    del params["price_total"]
                # del params["reservation_id"]
                pp.pprint(reservation_values)
                reservation.write(reservation_values)
            except Exception as e:
                return json.dumps(
                    {
                        "result": False,
                        "message": str(e),
                        "reservation": self.parse_reservation(reservation),
                    }
                )
            # print(parse_reservation(reservation))
            return json.dumps(
                {
                    "result": True,
                    "message": _("Operation completed successfully."),
                    "reservation": self.parse_reservation(reservation),
                }
            )
        else:
            return json.dumps({"result": False, "message": _("Reservation not found")})

    @http.route(
        "/calendar",
        type="http",
        auth="user",
        methods=["GET", "POST"],
        website=True,
    )
    def calendar(self, **post):
        date = datetime.datetime.now()
        date_start = date + timedelta(days=-1)
        if post.get("next_day"):
            date = datetime.datetime.strptime(
                post.get("next_day"), get_lang(request.env).date_format
            ).date()
            date_start = date + timedelta(days=+1)
        if post.get("previous_day"):
            date = datetime.datetime.strptime(
                post.get("previous_day"), get_lang(request.env).date_format
            ).date()
            date_start = date + timedelta(days=-1)
        if post.get("next_month"):
            date = datetime.datetime.strptime(
                post.get("next_month"), get_lang(request.env).date_format
            ).date()
            date_start = date + timedelta(days=30)
        if post.get("previous_month"):
            date = datetime.datetime.strptime(
                post.get("previous_month"), get_lang(request.env).date_format
            ).date()
            date_start = date + timedelta(days=-30)

        pms_property_id = request.env.user.get_active_property_ids()[0]
        Room = request.env["pms.room"]
        rooms = Room.search([("pms_property_id", "=", pms_property_id)])
        room_types = request.env["pms.room.type"].browse(
            rooms.mapped("room_type_id.id")
        )
        # Add default dpr and dpr_select_values
        dpr = 15
        if post.get("dpr"):
            dpr = int(post.get("dpr"))
        date_list = [date_start + timedelta(days=x) for x in range(dpr)]
        # get the days of the month
        month_days = monthrange(date.year, date.month)[1]
        dpr_select_values = {7, 15, month_days}
        Pricelist = request.env["product.pricelist"]
        pricelists = Pricelist.search(
            [
                "|",
                ("pms_property_ids", "=", False),
                ("pms_property_ids", "in", pms_property_id),
            ]
        )
        pricelist = (
            request.env["pms.property"].browse(pms_property_id).default_pricelist_id.id
        )
        if post and "pricelist" in post:
            pricelist = int(post["pricelist"])

        values = {
            "today": datetime.datetime.now(),
            "date_start": date_start,
            "page_name": "Calendar",
            "pricelist": pricelists,
            "default_pricelist": pricelist,
            "rooms_list": room_types,
            "date_list": date_list,
            "dpr": dpr,
            "dpr_select_values": dpr_select_values,
        }
        return http.request.render(
            "pms_pwa.roomdoo_calendar_page",
            values,
        )

    @http.route(
        "/calendar/line",
        type="json",
        auth="public",
        csrf=False,
        methods=["POST"],
        website=True,
    )
    def calendar_list(self, date=False, search="", **post):
        # TODO: Evitar el uso de eval
        dates = [item.date() for item in eval(post.get("range_date"))]
        from_date = min(dates)
        to_date = max(dates)
        pms_property_id = request.env.user.get_active_property_ids()[0]
        Reservation = request.env["pms.reservation"]
        ReservationLine = request.env["pms.reservation.line"]

        domain = [
            ("date", ">=", from_date),
            ("date", "<=", to_date),
            ("state", "!=", "cancelled"),
        ]
        reservation_lines = ReservationLine.search(domain)
        reservations = Reservation.browse(reservation_lines.mapped("reservation_id.id"))
        values = {}
        # REVIEW: revisar estructura
        values["reservations"] = []
        room_ids = (
            request.env["pms.room"]
            .search(
                [
                    ("pms_property_id", "=", pms_property_id),
                    ("room_type_id", "=", int(post.get("room_type_id"))),
                ]
            )
            .ids
        )
        for room_id in room_ids:
            free_dates = dates.copy()
            room = request.env["pms.room"].browse(room_id)
            rooms_reservation_values = []
            for reservation in reservations.filtered(
                lambda r: r.preferred_room_id.id == room_id
                and r.pms_property_id.id == pms_property_id
            ):
                min_reservation_date = min(
                    reservation.reservation_line_ids.filtered(
                        lambda d: d.date in dates
                    ).mapped("date")
                )
                max_reservation_date = max(
                    reservation.reservation_line_ids.filtered(
                        lambda d: d.date in dates
                    ).mapped("date")
                )
                for d in reservation.reservation_line_ids.mapped("date"):
                    if d in free_dates:
                        free_dates.remove(d)
                rooms_reservation_values.append(
                    {
                        "date": min_reservation_date,
                        "reservation_info": {
                            "id": reservation.id,
                            "partner_name": reservation.partner_id.name,
                            "img": "/web/image/res.partner/"
                            + str(reservation.partner_id.id)
                            + "/image_128",
                            "price": reservation.folio_pending_amount,
                            "status": "danger",  # TODO
                            "nigths": (
                                max_reservation_date
                                + timedelta(days=1)
                                - min_reservation_date
                            ).days,
                            "days": (
                                max_reservation_date
                                + timedelta(days=1)
                                - min_reservation_date
                            ).days
                            + 1,
                            "checkin_in_range": False
                            if min_reservation_date == reservation.checkin
                            else True,
                            "checkout_in_range": False
                            if max_reservation_date + timedelta(days=1)
                            != reservation.checkout
                            else True,
                        },
                    }
                )
            splitted_reservations_lines = reservations.filtered(
                lambda r: r.splitted
            ).reservation_line_ids.filtered(lambda l: l.room_id.id == room_id)
            for split in splitted_reservations_lines.sorted("date"):
                main_split = False
                reservation = split.reservation_id
                nights = 0
                if split.date == reservation.checkin:
                    main_split = True
                for date_iterator in [
                    split.date + timedelta(days=x)
                    for x in range(0, (reservation.checkout - split.date).days)
                ]:
                    line = reservation.reservation_line_ids(
                        lambda: l.date == date_iterator
                    )
                    if line and line.room_id == split.room_id:
                        nights += 1
                        free_dates.remove(line.date)
                        splitted_reservations_lines.remove(line)
                rooms_reservation_values.append(
                    {
                        "splitted": True,
                        "main_split": main_split,
                        "date": reservation.checkin,
                        "reservation_info": {
                            "id": reservation.id,
                            "partner_name": reservation.partner_id.name
                            if main_split
                            else False,
                            "img": "/web/image/res.partner/"
                            + str(reservation.partner_id.id)
                            + "/image_128"
                            if main_split
                            else False,
                            "price": reservation.folio_pending_amount
                            if main_split
                            else False,
                            "status": "danger",  # TODO
                            "nigths": nights,
                        },
                    }
                )
            for day in free_dates:
                rooms_reservation_values.append(
                    {
                        "date": day,
                        "reservation_info": False,
                    }
                )
            rooms_reservation_values = sorted(
                rooms_reservation_values, key=lambda item: item["date"]
            )
            for item in rooms_reservation_values:
                item["date"] = item["date"].strftime(get_lang(request.env).date_format)
            values["reservations"].append(
                {
                    "room": {
                        "id": room.id,
                        "room_type_id": room.room_type_id.id,
                        "name": room.name,
                        "status": "Limpia",  # TODO
                    },
                    "ocupation": rooms_reservation_values,
                }
            )
        pp.pprint(values)
        return values

    @http.route(
        ["/reservation/single_reservation_new"],
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def single_reservation_new(self, **kw):
        reservation_values = http.request.jsonrequest.get("params")
        print("reservation_values: {}".format(reservation_values))

        checkin = (
            datetime.datetime.strptime(
                reservation_values["checkin"], get_lang(request.env).date_format
            ).date()
            if "checkin" in reservation_values
            else datetime.datetime.today()
        )
        checkout = (
            datetime.datetime.strptime(
                reservation_values["checkout"].strip(),
                get_lang(request.env).date_format,
            ).date()
            if "checkout" in reservation_values
            else checkin + timedelta(days=1)
        )
        pms_property_id = False
        pms_property = False
        if request.env.user.get_active_property_ids():
            pms_property_id = request.env.user.get_active_property_ids()[0]
            pms_property = request.env["pms.property"].browse(pms_property_id)

        pricelist = False
        if reservation_values.get("pricelist_id"):
            pricelist = request.env["product.pricelist"].search(
                [("id", "=", int(reservation_values.get("pricelist_id")))]
            )
        if not pricelist and pms_property:
            pricelist = pms_property.default_pricelist_id

        # TODO: Search/create Partner
        partner = request.env["res.partner"].search([])[0]

        room_type_id = False
        if reservation_values.get("room_type_id"):
            room_type_id = request.env["pms.room.type"].search(
                [("id", "=", int(reservation_values.get("room_type_id")))]
            ).id

        vals = {
            "checkin": checkin,
            "checkout": checkout,
            "room_type_id": room_type_id,
            "pricelist_id": pricelist.id,
            "pms_property_id": pms_property.id if pms_property else False,
            "partner_id": partner.id if partner else False,
        }
        print(vals)
        if reservation_values.get("preferred_room_id"):
            vals["preferred_room_id"] = (
                request.env["pms.room"]
                .search([("id", "=", int(reservation_values.get("preferred_room_id")))])
                .id
            )

        if reservation_values.get("board_service_id"):
            vals["board_service_id"] = (
                request.env["pms.board.service.room.type"]
                .search([("id", "=", int(reservation_values.get("board_service_id")))])
                .id
            )

        if reservation_values.get("adults"):
            vals["adults"] = int(reservation_values.get("adults"))

        if reservation_values.get("channel_type_id"):
            vals["channel_type_id"] = int(reservation_values.get("channel_type_id"))

        if reservation_values.get("segmentation_id"):
            vals["segmentation_id"] = int(reservation_values.get("segmentation_id"))

        if reservation_values.get("agency_id"):
            vals["agency_id"] = int(reservation_values.get("agency_id"))
            vals["channel_type_id"] = request.env["res.partner"].browse(agency_id).sale_channel_id.id

        if reservation_values.get("submit"):
            reservation = request.env["pms.reservation"].create(vals)
            return self.parse_reservation(reservation)
        else:
            reservation = request.env["pms.reservation"].new(vals)
            reservation.flush()
            return self.parse_reservation(reservation)

    @http.route(
        ["/reservation/multiple_reservation_onchange"],
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def multiple_reservation_onchange(self, **kw):
        params = http.request.jsonrequest.get("params")
        folio_wizard = False
        print("params: {}".format(params))

        if params.get("id"):
            folio_wizard = request.env["pms.folio.wizard"].browse(int(params.get("id")))
        if folio_wizard:
            checkin = folio_wizard.start_date
            checkout = folio_wizard.end_date

        if not folio_wizard or params.get("checkin"):
            checkin = (
                datetime.datetime.strptime(
                    params["checkin"], get_lang(request.env).date_format
                ).date()
                if "checkin" in params
                else datetime.datetime.today().date()
            )
        if not folio_wizard or params.get("checkout"):
            checkout = (
                datetime.datetime.strptime(
                    params["checkout"].strip(),
                    get_lang(request.env).date_format,
                ).date()
                if "checkout" in params
                else checkin + timedelta(days=1).date()
            )

        pms_property = False
        pms_property_id = False
        if request.env.user.get_active_property_ids():
            pms_property_id = request.env.user.get_active_property_ids()[0]
            pms_property = request.env["pms.property"].browse(pms_property_id)
        # TODO: partner_id, diferenciar entre nuevo partner y
        # uno seleccionado (tipo direccion de facturacion en el detalle?)
        partner = request.env["res.partner"].search([])[0]
        pricelist = False
        if params.get("pricelist_id"):
            pricelist = request.env["product.pricelist"].search(
                [("id", "=", int(params.get("pricelist_id")))]
            )
        if not pricelist and pms_property:
            pricelist = pms_property.default_pricelist_id
        vals = {
            "start_date": checkin,
            "end_date": checkout,
            "pricelist_id": pricelist.id if pricelist else False,
            "pms_property_id": pms_property.id if pms_property else False,
            "partner_id": partner.id if partner else False,
        }
        if not folio_wizard:
            folio_wizard = request.env["pms.folio.wizard"].create(vals)
            folio_wizard.flush()
        if (
            checkin != folio_wizard.start_date
            or checkout != folio_wizard.end_date
            or pricelist.id != folio_wizard.pricelist_id.id
            or pms_property.id != folio_wizard.pms_property_id.id
            or partner.id != folio_wizard.partner_id.id
        ):
            folio_wizard.write(vals)
        if params.get("lines"):
            for line_id, values in params.get("lines").items():
                folio_wizard.availability_results.filtered(
                    lambda r: r.id == int(line_id)
                ).value_num_rooms_selected = int(values["value_num_rooms_selected"])
                folio_wizard.flush()
                # TODO: Board service

        return self.parse_wizard_folio(folio_wizard)

    @http.route(
        ["/reservation/multiple_reservation_new"],
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def multiple_reservation_new(self, **kw):
        params = http.request.jsonrequest.get("params")
        try:
            if params.get("id"):
                folio_wizard = self.env["pms.folio.wizard"].browse(params.get("id"))
            folio_action = folio_wizard.create_folio()
            return json.dumps(
                {
                    "result": True,
                    "message": _("Operation completed successfully."),
                    "id": folio_action["res_id"],
                }
            )
        except Exception as e:
            return json.dumps({"result": False, "message": str(e)})

    @http.route(
        "/calendar/config",
        type="http",
        auth="user",
        methods=["GET", "POST"],
        website=True,
    )
    def calendar_config(self, date=False, **post):
        date = datetime.datetime.now()
        date_start = date + timedelta(days=-1)
        if post.get("next_day"):
            date = datetime.datetime.strptime(
                post.get("next_day"), get_lang(request.env).date_format
            ).date()
            date_start = date + timedelta(days=+1)
        if post.get("previous_day"):
            date = datetime.datetime.strptime(
                post.get("previous_day"), get_lang(request.env).date_format
            ).date()
            date_start = date + timedelta(days=-1)
        if post.get("next_month"):
            date = datetime.datetime.strptime(
                post.get("next_month"), get_lang(request.env).date_format
            ).date()
            date_start = date + timedelta(days=30)
        if post.get("previous_month"):
            date = datetime.datetime.strptime(
                post.get("previous_month"), get_lang(request.env).date_format
            ).date()
            date_start = date + timedelta(days=-30)

        # Add default dpr and dpr_select_values
        dpr = 7
        if post.get("dpr"):
            dpr = int(post.get("dpr"))
        date_list = [date_start + timedelta(days=x) for x in range(dpr)]
        # get the days of the month
        month_days = monthrange(date.year, date.month)[1]
        dpr_select_values = {7, 15, month_days}

        Room = request.env["pms.room.type"]
        rooms = Room.search([])

        Pricelist = request.env["product.pricelist"]
        pricelist = Pricelist.search([])
        default_pricelist = pricelist[0].id
        if post and "pricelist" in post:
            default_pricelist = int(post["pricelist"])

        values = {
            "today": datetime.datetime.now(),
            "date_start": date_start,
            "page_name": "Calendar config",
            "pricelist": pricelist,
            "default_pricelist": default_pricelist,
            "rooms_list": rooms,
            "date_list": date_list,
            "dpr": dpr,
            "dpr_select_values": dpr_select_values,
        }
        return http.request.render(
            "pms_pwa.roomdoo_calendar_config_page",
            values,
        )

    @http.route(
        "/calendar/config/save",
        type="json",
        auth="public",
        csrf=False,
        methods=["POST"],
        website=True,
    )
    def calendar_config_list(self, date=False, search="", **post):
        params = http.request.jsonrequest.get("params")
        _logger.info(params)
        return True

    def parse_reservation(self, reservation):
        reservation_values = dict()
        reservation_values["id"] = reservation.id
        reservation_values["room_type_id"] = int(reservation.room_type_id.id)
        reservation_values["preferred_room_id"] = int(reservation.preferred_room_id.id)
        reservation_values["adults"] = reservation.adults
        reservation_values["reservation_type"] = reservation.folio_id.reservation_type
        reservation_values["checkin"] = reservation.checkin.strftime(
            get_lang(request.env).date_format
        )
        reservation_values["checkout"] = reservation.checkout.strftime(
            get_lang(request.env).date_format
        )
        reservation_values["arrival_hour"] = reservation.arrival_hour
        reservation_values["departure_hour"] = reservation.departure_hour
        reservation_values["price_total"] = reservation.price_room_services_set
        reservation_values["folio_pending_amount"] = reservation.folio_pending_amount
        reservation_values["pricelist_id"] = reservation.pricelist_id.id
        reservation_values["allowed_pricelists"] = reservation._get_allowed_pricelists()
        reservation_values["service_ids"] = reservation._get_service_ids()
        reservation_values[
            "allowed_board_service_room_ids"
        ] = reservation._get_allowed_board_service_room_ids()
        reservation_values["board_service_id"] = reservation.board_service_room_id.id
        reservation_values[
            "allowed_segmentations"
        ] = reservation._get_allowed_segmentations()
        reservation_values["segmentation_ids"] = reservation.segmentation_ids.ids
        reservation_values[
            "allowed_channel_type_ids"
        ] = self._get_allowed_channel_type_ids()
        reservation_values["channel_type_id"] = reservation.channel_type_id.id
        reservation_values["allowed_agency_ids"] = self._get_allowed_agency_ids()
        reservation_values["agency_id"] = reservation.agency_id.id
        reservation_values["room_numbers"] = rooms.Rooms._get_available_rooms(
            self=self,
            payload={
                "pms_property_id": reservation.pms_property_id.id,
                "pricelist_id": reservation.pricelist_id.id,
                "checkin": reservation_values["checkin"],
                "checkout": reservation_values["checkout"],
                "reservation_id": reservation.id,
            },
        )
        reservation_values[
            "room_types"
        ] = room_types.RoomTypes._get_available_room_types(
            self=self,
            payload={
                "pms_property_id": reservation.pms_property_id.id,
                "pricelist_id": reservation.pricelist_id.id,
                "checkin": reservation_values["checkin"],
                "checkout": reservation_values["checkout"],
                "reservation_id": reservation.id,
            },
        )
        _logger.info("Values from controller to Frontend (reservation onchange):")
        pp.pprint(reservation_values)
        return reservation_values

    def parse_params_record(self, origin_values, model):
        new_values = {}
        for k, v in origin_values.items():
            field = model._fields[k]
            if field.type in ("float", "monetary"):
                new_values[k] = float(v)
            if field.type in ("integer", "many2one"):
                new_values[k] = int(v)
            if field.type == "date":
                new_values[k] = datetime.datetime.strptime(
                    v, get_lang(request.env).date_format
                ).date()
            if field.type in ("one2many", "many2many"):
                relational_model = request.env[field.comodel_name]
                cmds = []
                for record_id, value in v.items():
                    cmds.append(
                        (
                            1,
                            int(record_id),
                            self.parse_params_record(
                                origin_values=value, model=relational_model
                            ),
                        )
                    )
                print("PARSE SERVICE LINES----------------------------------")
                print(cmds)
                new_values[k] = cmds
        return new_values

    def parse_wizard_folio(self, wizard):
        wizard_values = dict()
        wizard_values["id"] = wizard.id
        wizard_values["checkin"] = wizard.start_date.strftime(
            get_lang(request.env).date_format
        )
        wizard_values["checkout"] = wizard.end_date.strftime(
            get_lang(request.env).date_format
        )
        wizard_values["total_price_folio"] = wizard.total_price_folio
        wizard_values["discount"] = wizard.discount
        wizard_values["pricelist_id"] = wizard.pricelist_id.id
        wizard_values["allowed_pricelists"] = request.env[
            "pms.reservation"
        ]._get_allowed_pricelists()
        wizard_values["allowed_segmentations"] = request.env[
            "pms.reservation"
        ]._get_allowed_segmentations()
        wizard_values["allowed_channel_type_ids"] = self._get_allowed_channel_type_ids()
        wizard_values["allowed_agency_ids"] = self._get_allowed_agency_ids()

        lines = {}
        for line in wizard.availability_results:
            lines[line.id] = {
                "room_type_id": line.room_type_id.display_name,
                "num_rooms_available": line.num_rooms_available,
                "value_num_rooms_selected": line.value_num_rooms_selected,
                "price_per_room": line.price_per_room,
                "price_total": line.price_total,
            }
            # TODO: BoardService and boardservices allowed
            # "board_service_id" = line.board_service_id.id,
            # "allowed_board_service_room_ids" = \
            #     request.env["pms.room.type"]._get_allowed_board_service_room_ids(
            #         pms_room_type = line.room_type_id.id,
            #         pms_property_id = wizard.pms_property_id,
            #     ),
        wizard_values["lines"] = lines
        _logger.info("Values from controller to Frontend (multi reservation creation):")
        pp.pprint(wizard_values)

        return wizard_values
