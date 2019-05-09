# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero, float_compare, pycompat
import datetime

#CREAMOS UN MODELO PARA LA TABLA DONDE SE MOSTRARAN LAS NOTAS DE CREDITO DEL CLIENTE
class TablaNotas(models.Model):
	_name = 'tabla.notas'

	#AGREGAMOS LOS CAMPOS QUE TENDRA LA TABLA
	nombre = fields.Many2one('account.invoice', string='Rectificativa')
	cliente = fields.Char(string='Responsable')
	monto = fields.Float(string='Monto')
	tabla = fields.Many2one('sale.order')

	#MANDAMOS A TRAER EL NOMBRE DEL QUE CORRESPONDE LA NOTA, ASI COMO EL MONTO DE ESTA
	@api.onchange('nombre')
	def _onchange_nombre(self):
		self.cliente = self.nombre.partner_id.name
		self.monto = self.nombre.amount_total

class SaleOrder(models.Model):
	_inherit = "sale.order"

	lines_product = fields.Integer(string="Lineas de producto", compute="_get_lines")
	limite_superado = fields.Boolean(string="Limite superado")
	#AGREGAMOS LOS CAMPOS NECESARIOS A NUESTRA PAGINA DE NOTAS DE CREDITO
	disponibles = fields.Integer(string="Notas de credito disponibles", compute="_get_numero_notas")
	suma_montos = fields.Float(string="Monto total de sus notas de credito", compute="_get_numero_notas")
	tabla_notas = fields.One2many('tabla.notas', 'tabla')
	total = fields.Float(string='Total', compute="_get_total")

	#FUNCION PARA DETERMINAR EL NUMERO DE LINEAS DE PRODUCTOS AGREGADAS EN NUESTRA VENTA
	@api.depends('order_line')
	def _get_lines(self):
		lines = 0
		for line in self.order_line:
			lines += 1
			self.lines_product = lines
	#FUNCION PARA DETERMINAR CUANTAS NOTAS TIENE DISPONIBLE EL CLIENTE Y EL MONTO TOTAL DE ESTAS
	@api.depends('partner_id')
	def _get_numero_notas(self):
		notas = self.env['account.invoice'].search([('partner_id', '=', self.partner_id.id),('type','=','out_refund'),('state','=','open')])
		numero = 0
		sum_monto = 0.0
		for num in notas:
			numero += 1
			self.disponibles = numero

			sum_monto += num.amount_total
			self.suma_montos = sum_monto
	#FUNCION PARA CALCULAR EL MONTO TOTAL DE LAS NOTAS DE CREDITO APLICADAS EN NUESTRA VENTA
	@api.depends('tabla_notas')
	def _get_total(self):
		suma = 0.0
		for orde in self.tabla_notas:
			suma += orde.monto
			self.total = suma
	#MODIFICAMOS LA FUNCION NATIVA DE CREAR UNA FACTURA, PARA ENVIAR EL NUMERO DE NOTAS APLICADAS ASI COMO EL TOTAL DE ESTAS
	@api.multi
	def _prepare_invoice(self):

		numero_notas = 0
		monto_total = 0
		for rec in self.tabla_notas:
			numero_notas += 1
			monto_total += rec.nombre.amount_total

		self.ensure_one()
		journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
		if not journal_id:
			raise UserError(_('Please define an accounting sales journal for this company.'))

		invoice_vals = {
			'name': self.client_order_ref or '',
			'origin': self.name,
			'type': 'out_invoice',
			'account_id': self.partner_invoice_id.property_account_receivable_id.id,
			'partner_id': self.partner_invoice_id.id,
			'partner_shipping_id': self.partner_shipping_id.id,
			'journal_id': journal_id,
			'currency_id': self.pricelist_id.currency_id.id,
			'comment': self.note,
			'payment_term_id': self.payment_term_id.id,
			'fiscal_position_id': self.fiscal_position_id.id or self.partner_invoice_id.property_account_position_id.id,
			'company_id': self.company_id.id,
			'user_id': self.user_id and self.user_id.id,
			'team_id': self.team_id.id,
			'rectificativas': numero_notas,
			'credito_cliente': monto_total,
		}
		return invoice_vals	

	#EDITAMOS EL BOTON DE CONFIRMAR VENTA PARA COMPARAR EL MONTO DEL NOTA CON EL DE LA VENTA
	@api.one
	def action_confirm(self):
		if self.order_line:
			if self.tabla_notas:
				monto_venta = self.amount_total
				monto_notas = self.total
				if monto_notas > monto_venta:
					for line in self.tabla_notas:
						new_amount = self.total - (self.total - self.amount_total)
						restante_amount = self.total - self.amount_total
						actualizar = self.env['account.invoice'].search([('id', '=', line.nombre.id)], limit=1)
						for up in actualizar.invoice_line_ids:
							up.update({'price_unit': new_amount, 'price_subtotal': new_amount, 'invoice_line_tax_ids': [(5, [])]})	
						actualizar.update({
							'amount_untaxed': new_amount,
							'amount_tax': 0,
							'amount_total': new_amount,
							'residual': new_amount,
							'amount_total_signed': new_amount,
							'residual_signed': new_amount,
						})
					fecha_actual = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
					newnota_obj = self.env['account.invoice']
					newnota_values = {
						'partner_id': self.partner_id.id,
						'origin': 'GILSA1997',
						'date_invoice': fecha_actual,
						'type': 'out_refund',
					}
					newnota_id = newnota_obj.create(newnota_values)
					if newnota_id:
						product_type_nota = self.env['product.template'].search([('rectificativa_adeudada', '=', True)])
						line_newnota_obj = self.env['account.invoice.line']
						line_newnota_values = {
							'product_id': product_type_nota.id,
							'name': product_type_nota.name,
							'account_id': 1,
							'quantity': 1,
							'price_unit': restante_amount,
							'invoice_id': newnota_id.id,
						}
						line_newnota_id = line_newnota_obj.create(line_newnota_values)
						return super(SaleOrder, self).action_confirm()
				else:
					return super(SaleOrder, self).action_confirm()

class AccountInvoice(models.Model):
	_inherit = 'account.invoice'

	#AGREGAMOS LOS SIGUIENTES CAMPOS A LA VISTA DE FACTURAS
	rectificativas = fields.Integer(string="Rectificativas")
	credito_cliente = fields.Monetary(string="Credito a favor")

	#MODIFICAMOOS EL NOMBRE DEL DOCUMENTO DE FACTURACION
	@api.multi
	def name_get(self):
		result = []
		for record in self:
			record_name = str(record.number) + '   |   ' + str(record.amount_total)
			result.append((record.id, record_name))
		return result


	#MODIFICAMOS EL MONTO TOTAL DE LA FACTURA, RESTANDOLE EL MONTO DE LAS NOTAS DE CREDITO SELECCIONADAS EN LA VENTA
	@api.one
	@api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
				 'currency_id', 'company_id', 'date_invoice', 'type')
	def _compute_amount(self):
		round_curr = self.currency_id.round
		self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
		self.amount_tax = sum(round_curr(line.amount_total) for line in self.tax_line_ids)
		if self.credito_cliente > 0:
			self.amount_total = self.amount_untaxed + self.amount_tax - self.credito_cliente
		else:
			self.amount_total = self.amount_untaxed + self.amount_tax
		amount_total_company_signed = self.amount_total
		amount_untaxed_signed = self.amount_untaxed
		if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
			currency_id = self.currency_id.with_context(date=self.date_invoice)
			amount_total_company_signed = currency_id.compute(self.amount_total, self.company_id.currency_id)
			amount_untaxed_signed = currency_id.compute(self.amount_untaxed, self.company_id.currency_id)
		sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
		self.amount_total_company_signed = amount_total_company_signed * sign
		self.amount_total_signed = self.amount_total * sign
		self.amount_untaxed_signed = amount_untaxed_signed * sign

	#MODIFICAMOS EL MONTO RESIDUAL DE LA FACTURA, RESTANDOLE EL MONTO DE LAS NOTAS DE CREDITO SELECCIONADAS EN LA VENTA
	@api.one
	@api.depends(
		'state', 'currency_id', 'invoice_line_ids.price_subtotal',
		'move_id.line_ids.amount_residual',
		'move_id.line_ids.currency_id')
	def _compute_residual(self):
		residual = 0.0
		residual_company_signed = 0.0
		sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
		for line in self._get_aml_for_amount_residual():
			residual_company_signed += line.amount_residual
			if line.currency_id == self.currency_id:
				residual += line.amount_residual_currency if line.currency_id else line.amount_residual
			else:
				from_currency = (line.currency_id and line.currency_id.with_context(date=line.date)) or line.company_id.currency_id.with_context(date=line.date)
				residual += from_currency.compute(line.amount_residual, self.currency_id)
		self.residual_company_signed = abs(residual_company_signed) * sign
		self.residual_signed = abs(residual) * sign
		self.residual_signed -= self.credito_cliente#
		self.residual = abs(residual - self.credito_cliente) #
		digits_rounding_precision = self.currency_id.rounding
		if float_is_zero(self.residual, precision_rounding=digits_rounding_precision):
			self.reconciled = True
		else:
			self.reconciled = False	
	@api.one
	def action_invoice_open(self):
		date_payment = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		sale_order = self.env['sale.order'].search([('name', '=', self.origin)], limit=1)
		if sale_order:
			for line in sale_order.tabla_notas:
				#note = self.env["account.invoice"].search([('id', '=', self.refund_invoice_id.id),('type','=', 'out_refund')])
				payment_obj = self.env['account.payment']
				payment_values = {
					'invoice_ids': [(6,0, [line.nombre.id])],
					'payment_type': 'outbound',
					'partner_type': 'customer',
					'amount': line.nombre.amount_total,
					'journal_id': 1,
					'partner_id': line.nombre.partner_id.id,
					'payment_date': date_payment,
					'communication': line.nombre.number,
					'payment_method_id': 1,
				}
				payment_method_id = payment_obj.create(payment_values)
				payment_method_id.post()
		return super(AccountInvoice, self).action_invoice_open()		

#CREAMOS UN CAMPO DE TIPO BOLEANO PARA SELECCIONAR UN PRODUCTO APLICADO PARA UNA DEUDA DE NOTA DE CREDITO
class ProductTemplate(models.Model):
	_inherit = 'product.template'

	rectificativa_adeudada = fields.Boolean()


