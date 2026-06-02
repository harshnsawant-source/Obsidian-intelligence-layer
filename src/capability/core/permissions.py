def validate_permissions(

    declared_reads,
    declared_writes

):

    return {

        "reads": declared_reads,

        "writes": declared_writes,

        "status": "approved"

    }