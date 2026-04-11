# fixture: a worker that duplicates work on retry
# Represents iron-law violation #2: Oban will retry on transient failures,
# so non-idempotent workers cause duplicated emails / payments / side-effects.
defmodule MyApp.Workers.InvoiceWorker do
  use Oban.Worker, queue: :billing, max_attempts: 5

  alias MyApp.Billing
  alias MyApp.Mailer

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"invoice_id" => invoice_id}}) do
    invoice = Billing.get_invoice!(invoice_id)
    charge = Billing.charge_card(invoice.customer, invoice.amount_cents)
    Mailer.send_receipt(invoice.customer, charge)
    {:ok, charge}
  end
end
