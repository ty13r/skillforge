defmodule MyApp.Workers.InvoiceWorker do
  use Oban.Worker, queue: :billing, max_attempts: 5

  alias MyApp.Billing
  alias MyApp.Mailer

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"invoice_id" => invoice_id}}) do
    invoice = Billing.get_invoice!(invoice_id)

    if invoice.charged_at do
      :ok
    else
      {:ok, charge} = Billing.charge_card(invoice.customer, invoice.amount_cents)
      {:ok, _invoice} = Billing.mark_charged(invoice, charge.id)
      Mailer.send_receipt(invoice.customer, charge)
      :ok
    end
  end
end
