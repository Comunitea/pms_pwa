# Part of Odoo. See LICENSE file for full copyright and licensing details.

# -*- coding: utf-8 -*-

import base64
import json
import logging

from odoo import http, _
from odoo.http import request

from odoo.addons.web.controllers.main import Home
from odoo.osv import expression

_logger = logging.getLogger(__name__)

class Home(Home):
    @http.route()
    def index(self, *args, **kw):
        if request.session.uid and request.env["res.users"].sudo().browse(
            request.session.uid
        ).has_group("pms_pwa.group_pms_property_user"):
            return http.local_redirect(
                "/", query=request.params, keep_hash=True
            )
        return super(Home, self).index(*args, **kw)

    def _login_redirect(self, uid, redirect=None):
        if not redirect and request.env["res.users"].sudo().browse(uid).has_group(
            "pms_pwa.group_pms_property_user"
        ):
            return "/"
        return super(Home, self)._login_redirect(uid, redirect=redirect)


# Frontend controllers to test
class TestFrontEnd(http.Controller):
    @http.route(['/', '/page/<int:page>'], type='http', auth='public', methods=['GET'], website=True)
    def reservation_list(self, page=0, search="", sortby=None, **post):
        paginate_by = 10
        Reservation = request.env['pms.reservation']
        values = {}

        domain = self._get_search_domain(search, **post)

        partner = request.env.user.partner_id
        searchbar_sortings = {
            'priority': {'label': _('Priority'), 'order': 'priority desc'},
        }

        # default sortby order
        if not sortby:
            sortby = 'priority'
        sort_reservation = searchbar_sortings[sortby]['order']

        reservation_count = Reservation.search_count(domain)
        pager = request.website.pager(
            url='',
            total=reservation_count,
            page=page,
            step=paginate_by,
            scope=7,
            url_args=post)
        offset = pager['offset']

        reservations = Reservation.search(
            domain,
            order=sort_reservation,
            limit=paginate_by,
            offset=pager['offset'])

        values.update({
            'reservations': reservations,
            'page_name': 'Reservations',
            'pager': pager,
            'default_url': '',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })

        return http.request.render('pms_pwa.roomdoo_reservation_list', values)

    @http.route('/reservation/<int:reservation_id>', type='http', auth='public', website=True)
    def reservation_detail(self, reservation_id, **kw):
        reservation = request.env["pms.reservation"].browse([reservation_id])
        if not reservation:
            raise MissingError(_("This document does not exist."))
        values = {
            'page_name': 'Reservation',
            'invoice': reservation,
        }
        return http.request.render(
            'pms_pwa.roomdoo_reservation_detail',
            values,
            )

    @http.route(['/reservation/json_data'], type='json', auth="public", methods=['POST'], website=True)
    def reservation_detail_json(self, reservation_id=None, **kw):
        if reservation_id:
            reservation = request.env['pms.reservation'].sudo().search([('id', '=', int(reservation_id))])
        if not reservation:
            raise MissingError(_("This document does not exist."))
        allowed_rooms, allowed_room_types = reservation._get_allowed_rooms(
                checkin=reservation.checkin,
                checkout=reservation.checkout,
                state=reservation.state,
                overbooking=reservation.overbooking,
                line_ids=reservation.reservation_line_ids.ids
            )
        extras = reservation._get_allowed_extras(
                partner=reservation.partner_id,
                pricelist=reservation.pricelist_id
            )
        reservation_values = {
            'id': reservation.id,
            'partner_id': {
                'id': reservation.partner_id.id,
                'name': reservation.partner_id.name,
                'mobile': reservation.partner_id.mobile,
            },
            'unread_msg': 2,
            'messages': [
                'Lorem ipsum',
                'Unread short message',
            ],
            'room_type_id': {
                'id': reservation.room_type_id.id,
                'name': reservation.room_type_id.name,
            },
            'preferred_room_id': {
                'id': reservation.preferred_room_id.id if \
                    reservation.preferred_room_id else False,
                'name': reservation.preferred_room_id.name if \
                    reservation.preferred_room_id else reservation.rooms,
            },
            'extras': reservation._get_reservation_services(),
            'nights': reservation.nights,
            'reservation_line_ids': reservation._get_reservation_line_ids(),
            'checkin': reservation.checkin,
            'arrival_hour': reservation.arrival_hour,
            'checkout': reservation.checkout,
            'departure_hour': reservation.departure_hour,
            'folio_id': {
                'id': reservation.folio_id.id,
                'amount_total': reservation.folio_id.amount_total,
                'outstanding_vat': 15.69,
            },
            'state': reservation.state,
            'origin': reservation.origin,
            'detail_origin': reservation.detail_origin,
            'credit_card_details': reservation.credit_card_details,
            'price_total': reservation.price_total,
            'price_tax': reservation.price_tax,
            'folio_pending_amount': reservation.folio_pending_amount,
            'folio_internal_comment': reservation.folio_internal_comment,
            'allowed_room_type_ids': allowed_room_types,
            'allowed_room_ids': allowed_rooms,
            'extras': extras,
            'payment_methods': self._get_allowed_payments_journals(),
        }

        return reservation_values

    @http.route('/reservation/<int:id>/check-in', auth='public', website=True)
    def reservation_check_in(self, **kw):
        reservation = request.env["pms.reservation"].browse([reservation_id])
        if not reservation:
            raise MissingError(_("This document does not exist."))
        '''
            Ruta para realizar el checkin de la reserva 'id'
        '''
        pass

    @http.route('/reservation/<int:id>/check-out', auth='public', website=True)
    def reservation_check_out(self, **kw):
        reservation = request.env["pms.reservation"].browse([reservation_id])
        if not reservation:
            raise MissingError(_("This document does not exist."))
        '''
            Ruta para realizar el checkout de la reserva 'id'
        '''
        pass

    @http.route('/reservation/<int:id>/pay', auth='public', website=True)
    def reservation_pay(self, **kw):
        reservation = request.env["pms.reservation"].browse([reservation_id])
        if not reservation:
            raise MissingError(_("This document does not exist."))
        '''
            Ruta para realizar pago de la reserva 'id',
            ¿puede aceptar pagos parciales?
        '''
        pass

    @http.route('/reservation/<int:id>/assign', auth='public', website=True)
    def reservation_cancel(self, **kw):
        reservation = request.env["pms.reservation"].browse([reservation_id])
        if not reservation:
            raise MissingError(_("This document does not exist."))
        '''
            Ruta para realizar la cancelación de la reserva 'id'
        '''
        pass

    @http.route('/reservation/<int:id>/invoice', auth='public', website=True)
    def reservation_cancel(self, **kw):
        reservation = request.env["pms.reservation"].browse([reservation_id])
        if not reservation:
            raise MissingError(_("This document does not exist."))
        '''
            Ruta para realizar la cancelación de la reserva 'id'
        '''
        pass

    @http.route('/reservation/<int:id>/cancel', auth='public', website=True)
    def reservation_cancel(self, **kw):
        reservation = request.env["pms.reservation"].browse([reservation_id])
        if not reservation:
            raise MissingError(_("This document does not exist."))
        '''
            Ruta para realizar la cancelación de la reserva 'id'
        '''
        pass

    def _get_search_domain(self, search, **post):
        domains = []
        if search:
            for srch in search.split(" "):
                subdomains = [
                    [('localizator', 'ilike', srch)],
                    [('partner_id.phone', 'ilike', srch)],
                    [('partner_id.mobile', 'ilike', srch)],
                    [('partner_id.name', 'ilike', srch)],
                    [('partner_id.vat', 'ilike', srch)],
                    [('partner_id.email', 'ilike', srch)]
                ]
                domains.append(expression.OR(subdomains))
        #post send a filters with key: "operator&field"
        #to build a odoo domain:
        for k, v in post:
            domain.append((k[v.index('&'):],k[:v.index('&'),v]))
        return expression.AND(domains)

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
        payment_methods = request.env['account.journal'].sudo().search([
            ('type', 'in', ['bank','cash'])
            ])
        allowed_journals = []
        for journal in payment_methods:
            allowed_journals.append({
                'id': journal.id,
                'name': journal.name,
            })
        return allowed_journals

