CREATE TABLE requests (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    model         TEXT NOT NULL,
    prompt_hash   TEXT NOT NULL,
    input_tokens  INT NOT NULL,
    output_tokens INT NOT NULL,
    latency_ms    INT NOT NULL,
    cost_usd      NUMERIC(10, 6) NOT NULL,
    success       BOOLEAN NOT NULL,
    error_type    TEXT
);

CREATE TABLE eval_results (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id  UUID NOT NULL REFERENCES requests(id),
    eval_name   TEXT NOT NULL,
    passed      BOOLEAN NOT NULL,
    score       NUMERIC(5, 4),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_requests_created_at ON requests(created_at);
CREATE INDEX idx_requests_model ON requests(model);
CREATE INDEX idx_eval_results_request_id ON eval_results(request_id);