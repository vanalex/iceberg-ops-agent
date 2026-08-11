POLARIS_URL ?= http://localhost:8181
POLARIS_HEALTH_URL ?= http://localhost:8182
POLARIS_CLIENT_ID ?= root
POLARIS_CLIENT_SECRET ?= s3cr3t
POLARIS_REALM ?= POLARIS
MINIO_URL ?= http://localhost:9000
MINIO_ACCESS_KEY ?= minio_root
MINIO_SECRET_KEY ?= m1n1opwd
ICEBERG_VERSION ?= 1.11.0
ICEBERG_SPARK_RUNTIME ?= 4.1_2.13
DEFAULT_BASE_LOCATION ?= s3://warehouse
POLARIS_S3_ENDPOINT ?= http://localhost:9000
POLARIS_S3_ENDPOINT_INTERNAL ?= http://minio:9000
AWS_REGION ?= us-west-2

CATALOG ?= lakehouse
NAMESPACE ?= default
TABLE ?= events
PRINCIPAL ?= spark
PRINCIPAL_ROLE ?= spark_role
CATALOG_ROLE ?= catalog_admin

CURL := curl --silent --show-error --fail-with-body

.PHONY: help token catalogs catalog configure-catalog-storage principals \
        principal-roles catalog-roles health namespaces tables create-table \
        list-spark-tables table-health scan-table-health plan-table-maintenance clean

help:
	@echo "Polaris administration"
	@echo ""
	@echo "  make health"
	@echo "  make token"
	@echo "  make catalogs"
	@echo "  make catalog CATALOG=lakehouse"
	@echo "  make configure-catalog-storage CATALOG=lakehouse"
	@echo "  make principals"
	@echo "  make principal-roles"
	@echo "  make catalog-roles CATALOG=lakehouse"
	@echo "  make namespaces CATALOG=lakehouse"
	@echo "  make tables CATALOG=lakehouse NAMESPACE=default"
	@echo "  make create-table CATALOG=lakehouse"
	@echo "  make create-table CATALOG=lakehouse TABLE_SPECS=demo.events,demo.orders"
	@echo "  make list-spark-tables CATALOG=lakehouse"
	@echo "  make table-health CATALOG=lakehouse NAMESPACE=default TABLE=events"
	@echo "  make scan-table-health CATALOG=lakehouse"
	@echo "  make scan-table-health CATALOG=lakehouse TABLE_SPECS=demo.events,analytics.sessions"
	@echo "  make plan-table-maintenance CATALOG=lakehouse"
	@echo "  make plan-table-maintenance CATALOG=lakehouse TABLE_SPECS=demo.events"


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------

token:
	@$(CURL) \
		-X POST \
		-u "$(POLARIS_CLIENT_ID):$(POLARIS_CLIENT_SECRET)" \
		-H "Polaris-Realm: $(POLARIS_REALM)" \
		-H "Content-Type: application/x-www-form-urlencoded" \
		-d "grant_type=client_credentials" \
		-d "scope=PRINCIPAL_ROLE:ALL" \
		"$(POLARIS_URL)/api/catalog/v1/oauth/tokens" \
		| jq


define GET_TOKEN
$(shell curl --silent \
	-u "$(POLARIS_CLIENT_ID):$(POLARIS_CLIENT_SECRET)" \
	-H "Polaris-Realm: $(POLARIS_REALM)" \
	-d "grant_type=client_credentials" \
	-d "scope=PRINCIPAL_ROLE:ALL" \
	"$(POLARIS_URL)/api/catalog/v1/oauth/tokens" \
	| jq -r '.access_token')
endef


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------

health:
	@curl --silent --show-error --fail-with-body \
		"$(POLARIS_HEALTH_URL)/q/health" \
		| jq


# ---------------------------------------------------------
# Catalogs
# ---------------------------------------------------------

catalogs:
	@$(CURL) \
		-H "Authorization: Bearer $(GET_TOKEN)" \
		-H "Polaris-Realm: $(POLARIS_REALM)" \
		"$(POLARIS_URL)/api/management/v1/catalogs" \
		| jq


catalog:
	@$(CURL) \
		-H "Authorization: Bearer $(GET_TOKEN)" \
		-H "Polaris-Realm: $(POLARIS_REALM)" \
		"$(POLARIS_URL)/api/management/v1/catalogs/$(CATALOG)" \
		| jq


configure-catalog-storage:
	@tmp_file=$$(mktemp); \
	$(CURL) \
		-H "Authorization: Bearer $(GET_TOKEN)" \
		-H "Polaris-Realm: $(POLARIS_REALM)" \
		"$(POLARIS_URL)/api/management/v1/catalogs/$(CATALOG)" \
		> "$$tmp_file"; \
	entity_version=$$(jq -r '.entityVersion' "$$tmp_file"); \
	$(CURL) \
		-X PUT \
		-H "Authorization: Bearer $(GET_TOKEN)" \
		-H "Polaris-Realm: $(POLARIS_REALM)" \
		-H "Content-Type: application/json" \
		-d "$$(jq -n \
			--argjson currentEntityVersion "$$entity_version" \
			--arg defaultBaseLocation "$(DEFAULT_BASE_LOCATION)" \
			--arg region "$(AWS_REGION)" \
			--arg endpoint "$(POLARIS_S3_ENDPOINT)" \
			--arg endpointInternal "$(POLARIS_S3_ENDPOINT_INTERNAL)" \
			'{ \
				currentEntityVersion: $$currentEntityVersion, \
				properties: { "default-base-location": $$defaultBaseLocation }, \
				storageConfigInfo: { \
					storageType: "S3", \
					region: $$region, \
					endpoint: $$endpoint, \
					endpointInternal: $$endpointInternal, \
					pathStyleAccess: true, \
					stsUnavailable: true, \
					allowedLocations: [$$defaultBaseLocation] \
				} \
			}')" \
		"$(POLARIS_URL)/api/management/v1/catalogs/$(CATALOG)" \
		| jq; \
	rm -f "$$tmp_file"


# ---------------------------------------------------------
# Principals
# ---------------------------------------------------------

principals:
	@$(CURL) \
		-H "Authorization: Bearer $(GET_TOKEN)" \
		-H "Polaris-Realm: $(POLARIS_REALM)" \
		"$(POLARIS_URL)/api/management/v1/principals" \
		| jq


# ---------------------------------------------------------
# Principal roles
# ---------------------------------------------------------

principal-roles:
	@$(CURL) \
		-H "Authorization: Bearer $(GET_TOKEN)" \
		-H "Polaris-Realm: $(POLARIS_REALM)" \
		"$(POLARIS_URL)/api/management/v1/principal-roles" \
		| jq


# ---------------------------------------------------------
# Catalog roles
# ---------------------------------------------------------

catalog-roles:
	@$(CURL) \
		-H "Authorization: Bearer $(GET_TOKEN)" \
		-H "Polaris-Realm: $(POLARIS_REALM)" \
		"$(POLARIS_URL)/api/management/v1/catalogs/$(CATALOG)/catalog-roles" \
		| jq


# ---------------------------------------------------------
# Iceberg REST API
# ---------------------------------------------------------

namespaces:
	@$(CURL) \
		-H "Authorization: Bearer $(GET_TOKEN)" \
		-H "Polaris-Realm: $(POLARIS_REALM)" \
		"$(POLARIS_URL)/api/catalog/v1/$(CATALOG)/namespaces" \
		| jq


tables:
	@$(CURL) \
		-H "Authorization: Bearer $(GET_TOKEN)" \
		-H "Polaris-Realm: $(POLARIS_REALM)" \
		"$(POLARIS_URL)/api/catalog/v1/$(CATALOG)/namespaces/$(NAMESPACE)/tables" \
		| jq


create-table: configure-catalog-storage
	@PYTHONPATH="$(CURDIR)" \
	POLARIS_URL="$(POLARIS_URL)" \
	POLARIS_CLIENT_ID="$(POLARIS_CLIENT_ID)" \
	POLARIS_CLIENT_SECRET="$(POLARIS_CLIENT_SECRET)" \
	POLARIS_REALM="$(POLARIS_REALM)" \
	MINIO_URL="$(MINIO_URL)" \
	MINIO_ACCESS_KEY="$(MINIO_ACCESS_KEY)" \
	MINIO_SECRET_KEY="$(MINIO_SECRET_KEY)" \
	ICEBERG_VERSION="$(ICEBERG_VERSION)" \
	ICEBERG_SPARK_RUNTIME="$(ICEBERG_SPARK_RUNTIME)" \
	CATALOG="$(CATALOG)" \
	TABLE_SPECS="$(TABLE_SPECS)" \
	uv run python -m scripts.create_polaris_table


list-spark-tables:
	@PYTHONPATH="$(CURDIR)" \
	POLARIS_URL="$(POLARIS_URL)" \
	POLARIS_CLIENT_ID="$(POLARIS_CLIENT_ID)" \
	POLARIS_CLIENT_SECRET="$(POLARIS_CLIENT_SECRET)" \
	POLARIS_REALM="$(POLARIS_REALM)" \
	MINIO_URL="$(MINIO_URL)" \
	MINIO_ACCESS_KEY="$(MINIO_ACCESS_KEY)" \
	MINIO_SECRET_KEY="$(MINIO_SECRET_KEY)" \
	ICEBERG_VERSION="$(ICEBERG_VERSION)" \
	ICEBERG_SPARK_RUNTIME="$(ICEBERG_SPARK_RUNTIME)" \
	CATALOG="$(CATALOG)" \
	uv run python -m scripts.list_polaris_tables


table-health:
	@tmp_file=$$(mktemp); \
	http_code=$$(curl --silent --show-error \
		--output "$$tmp_file" \
		--write-out "%{http_code}" \
		-H "Authorization: Bearer $(GET_TOKEN)" \
		-H "Polaris-Realm: $(POLARIS_REALM)" \
		"$(POLARIS_URL)/api/catalog/v1/$(CATALOG)/namespaces/$(NAMESPACE)/tables/$(TABLE)"); \
	if [ "$$http_code" != "200" ]; then \
		echo "Failed to load Iceberg table metadata from Polaris."; \
		echo "HTTP status: $$http_code"; \
		echo "Catalog: $(CATALOG)"; \
		echo "Namespace: $(NAMESPACE)"; \
		echo "Table: $(TABLE)"; \
		echo ""; \
		echo "Polaris response:"; \
		jq . "$$tmp_file" 2>/dev/null || cat "$$tmp_file"; \
		echo ""; \
		echo "Check available namespaces with:"; \
		echo "  make namespaces CATALOG=$(CATALOG)"; \
		echo "Then list tables with:"; \
		echo "  make tables CATALOG=$(CATALOG) NAMESPACE=<namespace>"; \
		rm -f "$$tmp_file"; \
		exit 1; \
	fi; \
	jq '{ \
			catalog: "$(CATALOG)", \
			namespace: "$(NAMESPACE)", \
			table: "$(TABLE)", \
			metadata_location: ."metadata-location", \
			format_version: .metadata."format-version", \
			current_snapshot_id: .metadata."current-snapshot-id", \
			snapshot_count: (.metadata.snapshots // [] | length), \
			schema_count: (.metadata.schemas // [] | length), \
			partition_spec_count: (.metadata."partition-specs" // [] | length), \
			sort_order_count: (.metadata."sort-orders" // [] | length), \
			target_file_size_bytes: .metadata.properties."write.target-file-size-bytes", \
			delete_mode: .metadata.properties."write.delete.mode", \
			update_mode: .metadata.properties."write.update.mode", \
			merge_mode: .metadata.properties."write.merge.mode" \
		}' "$$tmp_file"; \
	rm -f "$$tmp_file"


scan-table-health:
	@PYTHONPATH="$(CURDIR)" \
	POLARIS_URL="$(POLARIS_URL)" \
	POLARIS_CLIENT_ID="$(POLARIS_CLIENT_ID)" \
	POLARIS_CLIENT_SECRET="$(POLARIS_CLIENT_SECRET)" \
	POLARIS_REALM="$(POLARIS_REALM)" \
	MINIO_URL="$(MINIO_URL)" \
	MINIO_ACCESS_KEY="$(MINIO_ACCESS_KEY)" \
	MINIO_SECRET_KEY="$(MINIO_SECRET_KEY)" \
	ICEBERG_VERSION="$(ICEBERG_VERSION)" \
	ICEBERG_SPARK_RUNTIME="$(ICEBERG_SPARK_RUNTIME)" \
	CATALOG="$(CATALOG)" \
	TABLE_SPECS="$(TABLE_SPECS)" \
	uv run python -m agent.src.collect_table_health


plan-table-maintenance:
	@PYTHONPATH="$(CURDIR)" \
	POLARIS_URL="$(POLARIS_URL)" \
	POLARIS_CLIENT_ID="$(POLARIS_CLIENT_ID)" \
	POLARIS_CLIENT_SECRET="$(POLARIS_CLIENT_SECRET)" \
	POLARIS_REALM="$(POLARIS_REALM)" \
	MINIO_URL="$(MINIO_URL)" \
	MINIO_ACCESS_KEY="$(MINIO_ACCESS_KEY)" \
	MINIO_SECRET_KEY="$(MINIO_SECRET_KEY)" \
	ICEBERG_VERSION="$(ICEBERG_VERSION)" \
	ICEBERG_SPARK_RUNTIME="$(ICEBERG_SPARK_RUNTIME)" \
	CATALOG="$(CATALOG)" \
	TABLE_SPECS="$(TABLE_SPECS)" \
	OPENAI_MODEL="$(OPENAI_MODEL)" \
	uv run python -m agent.src.plan_table_maintenance
