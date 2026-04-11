# golden: Decimal-safe Oban args with string keys and round-trip helpers
defmodule MyApp.Workers.LedgerWorker do
  use Oban.Worker, queue: :ledger, max_attempts: 5

  alias MyApp.Ledger

  def enqueue_credit(account_id, %Decimal{} = amount) do
    %{
      "account_id" => account_id,
      "amount" => Decimal.to_string(amount),
      "currency" => "USD"
    }
    |> new()
    |> Oban.insert()
  end

  @impl Oban.Worker
  def perform(%Oban.Job{
        args: %{
          "account_id" => account_id,
          "amount" => amount_str,
          "currency" => "USD"
        }
      }) do
    amount = Decimal.new(amount_str)
    Ledger.credit(account_id, amount)
  end
end
