.PHONY: dev-db dev-up dev-down migrate test build-frontend prod-smoke-test

dev-db:
	docker compose up -d db

dev-up:
	docker compose up -d db backend frontend

dev-down:
	docker compose down

migrate:
	flask --app wsgi db upgrade

test:
	pytest backend/tests -v

build-frontend:
	./scripts/build_frontend.sh

prod-smoke-test: build-frontend
	FLASK_ENV=production flask --app wsgi run
