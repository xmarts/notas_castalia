# -*- coding: utf-8 -*-
from odoo import http

# class Castalia(http.Controller):
#     @http.route('/castalia/castalia/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/castalia/castalia/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('castalia.listing', {
#             'root': '/castalia/castalia',
#             'objects': http.request.env['castalia.castalia'].search([]),
#         })

#     @http.route('/castalia/castalia/objects/<model("castalia.castalia"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('castalia.object', {
#             'object': obj
#         })